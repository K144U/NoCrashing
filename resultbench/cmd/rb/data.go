package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
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
	if err := parse(fs, args); err != nil {
		return err
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
