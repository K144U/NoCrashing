// Package publish holds the pre-release materialization pipeline (designs C1,
// C2 and the pre-warmed cache B3) and the correction pipeline that pushes
// revised results to each store after release.
package publish

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"

	"github.com/k144u/nocrashing/resultbench/internal/dataset"
	"github.com/k144u/nocrashing/resultbench/internal/db"
	"github.com/k144u/nocrashing/resultbench/internal/portal"
)

// Target says where materialized results go.
type Target string

const (
	TargetKV    Target = "kv"    // C1: raw JSON in Redis, no expiry
	TargetCache Target = "cache" // B3: cache-aside entries in Redis, with TTL
	TargetFiles Target = "files" // C2: one JSON file per roll number for Nginx
)

// Options for one materialization run.
type Options struct {
	Target   Target
	Redis    *redis.Client
	Dir      string        // for TargetFiles
	CacheTTL time.Duration // for TargetCache
	// Fraction of students to publish now (1.0 = all). The rest are published
	// after Resume, which models release happening before the pipeline ends.
	Fraction float64
	Seed     uint64
}

// Report summarises a run.
type Report struct {
	Target      Target  `json:"target"`
	Written     int     `json:"written"`
	Deferred    int     `json:"deferred"`
	Seconds     float64 `json:"seconds"`
	PerSecond   float64 `json:"per_second"`
	Bytes       int64   `json:"bytes"`
	Complete    bool    `json:"complete"`
	VerifiedOK  int     `json:"verified_ok,omitempty"`
	VerifiedBad int     `json:"verified_bad,omitempty"`
}

// ShardPath returns the file path for a roll number under dir. Files are
// spread over subdirectories of 1000 so no directory gets too large.
func ShardPath(dir string, roll int64) string {
	return filepath.Join(dir, strconv.FormatInt(roll/1000, 10), strconv.FormatInt(roll, 10)+".json")
}

// deferred reports whether a record is held back when Fraction < 1. The
// choice is a deterministic hash so the oracle-independent analysis can
// reproduce which roll numbers were missing.
func deferred(roll int64, fraction float64, seed uint64) bool {
	if fraction >= 1 {
		return false
	}
	h := uint64(roll)*0x9E3779B97F4A7C15 ^ seed
	h ^= h >> 31
	return float64(h%10000)/10000 >= fraction
}

// Materialize reads every result from the database and writes it to the
// target. It returns the records it deferred so Resume can finish the job.
func Materialize(ctx context.Context, pool *pgxpool.Pool, o Options) (Report, []dataset.Record, error) {
	start := time.Now()
	rep := Report{Target: o.Target}
	var later []dataset.Record
	w, err := newWriter(o)
	if err != nil {
		return rep, nil, err
	}
	err = db.Stream(ctx, pool, func(rec dataset.Record) error {
		if deferred(rec.Roll, o.Fraction, o.Seed) {
			later = append(later, rec)
			return nil
		}
		n, err := w.put(ctx, rec)
		rep.Written++
		rep.Bytes += int64(n)
		return err
	})
	if err == nil {
		err = w.flush(ctx)
	}
	rep.Deferred = len(later)
	rep.Complete = len(later) == 0 && err == nil
	rep.Seconds = time.Since(start).Seconds()
	if rep.Seconds > 0 {
		rep.PerSecond = float64(rep.Written) / rep.Seconds
	}
	return rep, later, err
}

// Resume publishes records that Materialize deferred.
func Resume(ctx context.Context, o Options, recs []dataset.Record) (Report, error) {
	start := time.Now()
	rep := Report{Target: o.Target}
	w, err := newWriter(o)
	if err != nil {
		return rep, err
	}
	for _, rec := range recs {
		n, err := w.put(ctx, rec)
		if err != nil {
			return rep, err
		}
		rep.Written++
		rep.Bytes += int64(n)
	}
	err = w.flush(ctx)
	rep.Complete = err == nil
	rep.Seconds = time.Since(start).Seconds()
	return rep, err
}

// Verify checks a sample of published records against the dataset. A board
// would run this before release; it is the "completeness check".
func Verify(ctx context.Context, o Options, cfg dataset.Config, step int) (ok, bad int, err error) {
	if step <= 0 {
		step = 1
	}
	for i := 0; i < cfg.N; i += step {
		want := dataset.Fingerprint(cfg.Original(i))
		var body []byte
		roll := cfg.Roll(i)
		switch o.Target {
		case TargetFiles:
			body, err = os.ReadFile(ShardPath(o.Dir, roll))
			if os.IsNotExist(err) {
				bad++
				err = nil
				continue
			}
		case TargetKV:
			body, err = o.Redis.Get(ctx, portal.Key(roll)).Bytes()
			if err == redis.Nil {
				bad++
				err = nil
				continue
			}
		default:
			return ok, bad, fmt.Errorf("verify not supported for %s", o.Target)
		}
		if err != nil {
			return ok, bad, err
		}
		if got, perr := fingerprintOf(body); perr == nil && got == want {
			ok++
		} else {
			bad++
		}
	}
	return ok, bad, nil
}

// CorrectionReport records the timings of a correction batch, so the
// staleness window can be reported.
type CorrectionReport struct {
	Rolls          int     `json:"rolls"`
	DBSeconds      float64 `json:"db_seconds"`
	PushSeconds    float64 `json:"push_seconds"`
	Invalidated    bool    `json:"invalidated"`
	StartedUnixMs  int64   `json:"started_unix_ms"`
	FinishedUnixMs int64   `json:"finished_unix_ms"`
}

// Correct applies the correction batch in the database (or, with revert,
// restores the originals) and, when invalidate is set, pushes the change to
// the target store: deleting cache-aside entries, or rewriting pre-computed
// ones.
func Correct(ctx context.Context, pool *pgxpool.Pool, cfg dataset.Config, o Options, invalidate, revert bool) (CorrectionReport, error) {
	rep := CorrectionReport{StartedUnixMs: time.Now().UnixMilli(), Invalidated: invalidate}
	t0 := time.Now()
	rolls, err := db.ApplyCorrections(ctx, pool, cfg, revert)
	if err != nil {
		return rep, err
	}
	rep.Rolls = len(rolls)
	rep.DBSeconds = time.Since(t0).Seconds()
	t1 := time.Now()
	if invalidate && o.Target != "" {
		switch o.Target {
		case TargetCache:
			// Cache-aside invalidation: delete, the next read refills.
			pipe := o.Redis.Pipeline()
			for _, roll := range rolls {
				pipe.Del(ctx, portal.Key(roll))
			}
			if _, err := pipe.Exec(ctx); err != nil {
				return rep, err
			}
		default:
			// Pre-computed stores must be rewritten with the new values.
			w, err := newWriter(o)
			if err != nil {
				return rep, err
			}
			for _, roll := range rolls {
				idx, _ := cfg.Valid(roll)
				if _, err := w.put(ctx, cfg.Current(idx, !revert)); err != nil {
					return rep, err
				}
			}
			if err := w.flush(ctx); err != nil {
				return rep, err
			}
		}
	}
	rep.PushSeconds = time.Since(t1).Seconds()
	rep.FinishedUnixMs = time.Now().UnixMilli()
	return rep, nil
}

type writer struct {
	o    Options
	pipe redis.Pipeliner
	n    int
	dirs map[string]bool
}

func newWriter(o Options) (*writer, error) {
	w := &writer{o: o, dirs: map[string]bool{}}
	switch o.Target {
	case TargetKV, TargetCache:
		if o.Redis == nil {
			return nil, fmt.Errorf("target %s needs redis", o.Target)
		}
		w.pipe = o.Redis.Pipeline()
	case TargetFiles:
		if o.Dir == "" {
			return nil, fmt.Errorf("target files needs a directory")
		}
	default:
		return nil, fmt.Errorf("unknown target %q", o.Target)
	}
	return w, nil
}

func (w *writer) put(ctx context.Context, rec dataset.Record) (int, error) {
	body := dataset.JSON(rec)
	switch w.o.Target {
	case TargetKV:
		w.pipe.Set(ctx, portal.Key(rec.Roll), body, 0)
	case TargetCache:
		entry := portal.EncodeCacheEntry(body, 5*time.Millisecond, time.Now().Add(w.o.CacheTTL))
		w.pipe.Set(ctx, portal.Key(rec.Roll), entry, w.o.CacheTTL)
	case TargetFiles:
		path := ShardPath(w.o.Dir, rec.Roll)
		dir := filepath.Dir(path)
		if !w.dirs[dir] {
			if err := os.MkdirAll(dir, 0o755); err != nil {
				return 0, err
			}
			w.dirs[dir] = true
		}
		// Write to a temporary file and rename, so Nginx never serves a
		// half-written result.
		tmp := path + ".tmp"
		if err := os.WriteFile(tmp, body, 0o644); err != nil {
			return 0, err
		}
		return len(body), os.Rename(tmp, path)
	}
	w.n++
	if w.n%1000 == 0 {
		if err := w.flush(ctx); err != nil {
			return 0, err
		}
	}
	return len(body), nil
}

func (w *writer) flush(ctx context.Context) error {
	if w.pipe == nil {
		return nil
	}
	_, err := w.pipe.Exec(ctx)
	if err == redis.Nil {
		err = nil
	}
	return err
}
