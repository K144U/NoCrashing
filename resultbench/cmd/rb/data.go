package main

import (
	"bufio"
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/k144u/nocrashing/resultbench/internal/dataset"
	"github.com/k144u/nocrashing/resultbench/internal/db"
	"github.com/k144u/nocrashing/resultbench/internal/publish"
)

func writeReport(path string, v any) error {
	b, _ := json.MarshalIndent(v, "", "  ")
	fmt.Println(string(b))
	if path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}

func runDBLoad(args []string) error {
	fs := flag.NewFlagSet("dbload", flag.ExitOnError)
	dsn := fs.String("dsn", "postgres://rb:rb@postgres:5432/rb", "PostgreSQL DSN")
	force := fs.Bool("force", false, "reload even if the same dataset is present")
	cfg := datasetFlags(fs)
	if err := parse(fs, args); err != nil {
		return err
	}
	ctx, stop := signalContext()
	defer stop()
	pool, err := db.Connect(ctx, *dsn, 4)
	if err != nil {
		return err
	}
	defer pool.Close()
	if err := db.WaitReady(ctx, pool, 2*time.Minute); err != nil {
		return err
	}
	start := time.Now()
	skipped, err := db.Load(ctx, pool, *cfg, *force, func(done int) {
		log.Printf("loaded %d/%d students (%.0f/s)", done, cfg.N, float64(done)/time.Since(start).Seconds())
	})
	if err != nil {
		return err
	}
	if skipped {
		log.Printf("dataset seed=%d n=%d already loaded; nothing to do", cfg.Seed, cfg.N)
		return nil
	}
	log.Printf("loaded %d students in %.1fs", cfg.N, time.Since(start).Seconds())
	return nil
}

func publishFlags(fs *flag.FlagSet) (*publish.Options, *string, *string) {
	o := &publish.Options{}
	target := fs.String("target", "kv", "kv | cache | files")
	redisAddr := fs.String("redis", "redis:6379", "Redis address (kv, cache)")
	fs.StringVar(&o.Dir, "dir", "/data/results", "output directory (files)")
	fs.DurationVar(&o.CacheTTL, "cache-ttl", 10*time.Minute, "entry lifetime (cache)")
	return o, target, redisAddr
}

func runMaterialize(args []string) error {
	fs := flag.NewFlagSet("materialize", flag.ExitOnError)
	dsn := fs.String("dsn", "postgres://rb:rb@postgres:5432/rb", "PostgreSQL DSN")
	o, target, redisAddr := publishFlags(fs)
	fs.Float64Var(&o.Fraction, "fraction", 1, "fraction of results to publish before release")
	release := fs.String("release-at", "", "with fraction < 1: publish the rest after this time (Unix ms)")
	verifyStep := fs.Int("verify-step", 0, "after publishing, check every Nth record against the dataset (0: skip)")
	report := fs.String("report", "", "write the JSON report here")
	if err := parse(fs, args); err != nil {
		return err
	}
	o.Target = publish.Target(*target)
	ctx, stop := signalContext()
	defer stop()
	pool, err := db.Connect(ctx, *dsn, 4)
	if err != nil {
		return err
	}
	defer pool.Close()
	if err := db.WaitReady(ctx, pool, 2*time.Minute); err != nil {
		return err
	}
	cfg, ok, err := db.LoadedConfig(ctx, pool)
	if err != nil || !ok {
		return fmt.Errorf("no complete dataset in the database (run rb dbload first): %v", err)
	}
	o.Seed = cfg.Seed
	if o.Target != publish.TargetFiles {
		o.Redis = newRedis(*redisAddr, 8)
		defer o.Redis.Close()
	}
	out := map[string]any{}
	rep, later, err := publish.Materialize(ctx, pool, *o)
	if err != nil {
		return err
	}
	if *verifyStep > 0 && rep.Complete {
		rep.VerifiedOK, rep.VerifiedBad, err = publish.Verify(ctx, *o, cfg, *verifyStep)
		if err != nil {
			return err
		}
		if rep.VerifiedBad > 0 {
			log.Printf("WARNING: completeness check found %d bad or missing records", rep.VerifiedBad)
		}
	}
	out["before_release"] = rep
	if len(later) > 0 {
		releaseAt, err := epochMs(*release)
		if err != nil {
			return err
		}
		// Write the first report now so the runner can read preparation time.
		if err := writeReport(*report, out); err != nil {
			return err
		}
		if err := waitUntil(ctx, releaseAt); err != nil {
			return err
		}
		rest, err := publish.Resume(ctx, *o, later)
		if err != nil {
			return err
		}
		out["after_release"] = rest
	}
	return writeReport(*report, out)
}

func runCorrect(args []string) error {
	fs := flag.NewFlagSet("correct", flag.ExitOnError)
	dsn := fs.String("dsn", "postgres://rb:rb@postgres:5432/rb", "PostgreSQL DSN")
	o, target, redisAddr := publishFlags(fs)
	invalidate := fs.Bool("invalidate", true, "push the change to the store (delete cache entries / rewrite pre-computed ones)")
	revert := fs.Bool("revert", false, "restore the original results")
	at := fs.String("at", "", "wait until this time (Unix ms) before starting")
	report := fs.String("report", "", "write the JSON report here")
	if err := parse(fs, args); err != nil {
		return err
	}
	o.Target = publish.Target(*target)
	if *target == "none" {
		o.Target = ""
	}
	ctx, stop := signalContext()
	defer stop()
	pool, err := db.Connect(ctx, *dsn, 4)
	if err != nil {
		return err
	}
	defer pool.Close()
	cfg, ok, err := db.LoadedConfig(ctx, pool)
	if err != nil || !ok {
		return fmt.Errorf("no complete dataset in the database: %v", err)
	}
	if o.Target == publish.TargetKV || o.Target == publish.TargetCache {
		o.Redis = newRedis(*redisAddr, 8)
		defer o.Redis.Close()
	}
	t, err := epochMs(*at)
	if err != nil {
		return err
	}
	if err := waitUntil(ctx, t); err != nil {
		return err
	}
	rep, err := publish.Correct(ctx, pool, cfg, *o, *invalidate, *revert)
	if err != nil {
		return err
	}
	return writeReport(*report, rep)
}

func runRelease(args []string) error {
	fs := flag.NewFlagSet("release", flag.ExitOnError)
	at := fs.String("at", "", "release time (Unix ms); empty: release now")
	path := fs.String("flag", "/data/released", "flag file to create at release")
	exit := fs.Bool("exit", false, "exit after release instead of idling")
	requireAt := fs.Bool("require-at", false, "refuse to start without a release time (production)")
	if err := parse(fs, args); err != nil {
		return err
	}
	if *requireAt && (*at == "" || *at == "0") {
		return fmt.Errorf("no release time: set RB_AT (Unix milliseconds); refusing to release immediately")
	}
	ctx, stop := signalContext()
	defer stop()
	if err := os.Remove(*path); err != nil && !os.IsNotExist(err) {
		return err
	}
	t, err := epochMs(*at)
	if err != nil {
		return err
	}
	if err := waitUntil(ctx, t); err != nil {
		return err
	}
	if err := os.WriteFile(*path, []byte(time.Now().Format(time.RFC3339Nano)+"\n"), 0o644); err != nil {
		return err
	}
	log.Printf("released: created %s", *path)
	if !*exit {
		<-ctx.Done()
	}
	return nil
}

func runSample(args []string) error {
	fs := flag.NewFlagSet("sample", flag.ExitOnError)
	count := fs.Int("count", 3, "number of records to print")
	corrected := fs.Bool("corrected", false, "print only students with a correction, showing both versions")
	cfg := datasetFlags(fs)
	if err := parse(fs, args); err != nil {
		return err
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	shown := 0
	for i := 0; i < cfg.N && shown < *count; i++ {
		if *corrected {
			if !cfg.IsCorrected(i) {
				continue
			}
			enc.Encode(map[string]dataset.Record{"original": cfg.Original(i), "corrected": cfg.Corrected(i)})
		} else {
			enc.Encode(cfg.Original(i))
		}
		shown++
	}
	return nil
}

func runFetch(args []string) error {
	fs := flag.NewFlagSet("fetch", flag.ExitOnError)
	timeout := fs.Duration("timeout", 10*time.Second, "request timeout")
	if err := parse(fs, args); err != nil {
		return err
	}
	c := &http.Client{Timeout: *timeout}
	for _, u := range fs.Args() {
		resp, err := c.Get(u)
		if err != nil {
			return err
		}
		_, err = io.Copy(os.Stdout, resp.Body)
		resp.Body.Close()
		if err != nil {
			return err
		}
		if resp.StatusCode >= 400 {
			return fmt.Errorf("%s: status %d", u, resp.StatusCode)
		}
	}
	return nil
}

// runPublishCSV turns a board's own results file into static result files
// for Nginx (the result-in-a-box deployment). Header:
//
//	roll,name,father_name,school_code,school_name,district,HIN:Hindi,ENG:English,...
//
// Every column after district is a subject written as CODE:Name, holding marks.
func runPublishCSV(args []string) error {
	fs := flag.NewFlagSet("publish-csv", flag.ExitOnError)
	in := fs.String("in", "", "results CSV")
	dir := fs.String("dir", "/data/results", "output directory")
	verify := fs.Bool("verify", true, "read every file back and compare after writing")
	if err := parse(fs, args); err != nil {
		return err
	}
	if *in == "" {
		return fmt.Errorf("-in is required")
	}
	f, err := os.Open(*in)
	if err != nil {
		return err
	}
	defer f.Close()
	r := csv.NewReader(bufio.NewReader(f))
	header, err := r.Read()
	if err != nil {
		return err
	}
	const fixed = 6
	if len(header) <= fixed || header[0] != "roll" {
		return fmt.Errorf("header must start with roll,name,father_name,school_code,school_name,district and then subjects")
	}
	var subjects []dataset.Subject
	for _, h := range header[fixed:] {
		code, name, ok := strings.Cut(h, ":")
		if !ok {
			return fmt.Errorf("subject column %q must be CODE:Name", h)
		}
		subjects = append(subjects, dataset.Subject{Code: code, Name: name})
	}
	start := time.Now()
	seen := map[int64]bool{}
	var recs []dataset.Record
	for line := 2; ; line++ {
		row, err := r.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("line %d: %w", line, err)
		}
		roll, err := strconv.ParseInt(row[0], 10, 64)
		if err != nil || roll < 1000 {
			return fmt.Errorf("line %d: bad roll number %q (need at least 4 digits)", line, row[0])
		}
		if seen[roll] {
			return fmt.Errorf("line %d: duplicate roll number %d", line, roll)
		}
		seen[roll] = true
		school, _ := strconv.Atoi(row[3])
		rec := dataset.Record{Roll: roll, Name: row[1], FatherName: row[2], SchoolCode: school, SchoolName: row[4],
			District: row[5], Version: 1}
		for k, s := range subjects {
			m, err := strconv.Atoi(strings.TrimSpace(row[fixed+k]))
			if err != nil || m < 0 || m > 100 {
				return fmt.Errorf("line %d: bad marks %q for %s", line, row[fixed+k], s.Code)
			}
			rec.Marks = append(rec.Marks, dataset.Mark{Code: s.Code, Name: s.Name, Marks: m})
		}
		dataset.Finalize(&rec)
		recs = append(recs, rec)
	}
	ctx, stop := signalContext()
	defer stop()
	o := publish.Options{Target: publish.TargetFiles, Dir: *dir, Fraction: 1}
	rep, err := publish.Resume(ctx, o, recs)
	if err != nil {
		return err
	}
	rep.Seconds = time.Since(start).Seconds()
	if *verify {
		for _, rec := range recs {
			b, err := os.ReadFile(publish.ShardPath(*dir, rec.Roll))
			if err != nil {
				rep.VerifiedBad++
				continue
			}
			var got dataset.Record
			if json.Unmarshal(b, &got) != nil || dataset.Fingerprint(got) != dataset.Fingerprint(rec) {
				rep.VerifiedBad++
			} else {
				rep.VerifiedOK++
			}
		}
		if rep.VerifiedBad > 0 {
			return fmt.Errorf("verification failed for %d of %d results", rep.VerifiedBad, len(recs))
		}
	}
	return writeReport("", rep)
}
