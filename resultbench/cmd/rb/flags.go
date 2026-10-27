package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/k144u/nocrashing/resultbench/internal/dataset"
)

// parse parses args and then fills any flag not given on the command line
// from the environment variable RB_<NAME> (dashes become underscores).
func parse(fs *flag.FlagSet, args []string) error {
	if err := fs.Parse(args); err != nil {
		return err
	}
	set := map[string]bool{}
	fs.Visit(func(f *flag.Flag) { set[f.Name] = true })
	var err error
	fs.VisitAll(func(f *flag.Flag) {
		if set[f.Name] || err != nil {
			return
		}
		env := "RB_" + strings.ToUpper(strings.ReplaceAll(f.Name, "-", "_"))
		if v, ok := os.LookupEnv(env); ok {
			if e := fs.Set(f.Name, v); e != nil {
				err = fmt.Errorf("%s: %w", env, e)
			}
		}
	})
	return err
}

// datasetFlags registers the flags that identify a dataset.
func datasetFlags(fs *flag.FlagSet) *dataset.Config {
	d := dataset.Default()
	cfg := &d
	fs.Uint64Var(&cfg.Seed, "seed", d.Seed, "dataset seed")
	fs.IntVar(&cfg.N, "n", d.N, "number of students")
	fs.Int64Var(&cfg.RollBase, "roll-base", d.RollBase, "roll number of the first student")
	fs.IntVar(&cfg.CorrectionPerMille, "correction-per-mille", d.CorrectionPerMille, "students per 1000 with a revised result")
	fs.IntVar(&cfg.NumSchools, "schools", d.NumSchools, "number of schools")
	return cfg
}

// epochMs parses a release time: empty or 0 means none, otherwise Unix ms.
func epochMs(s string) (time.Time, error) {
	if s == "" || s == "0" {
		return time.Time{}, nil
	}
	ms, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return time.Time{}, fmt.Errorf("release time must be Unix milliseconds: %w", err)
	}
	return time.UnixMilli(ms), nil
}

func signalContext() (context.Context, context.CancelFunc) {
	return signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
}

func waitUntil(ctx context.Context, t time.Time) error {
	if t.IsZero() {
		return nil
	}
	if d := time.Until(t); d > 0 {
		log.Printf("waiting %.1fs until %s", d.Seconds(), t.Format(time.RFC3339Nano))
		select {
		case <-time.After(d):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	return nil
}
