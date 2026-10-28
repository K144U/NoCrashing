package main

import (
	"flag"
	"fmt"
	"log"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/k144u/nocrashing/resultbench/internal/surge"
)

// surgeOverrides are the scenario fields the runner sets per run.
type surgeOverrides struct {
	targets   *string
	releaseAt *int64
	peak      *float64
	seed      *uint64
	name      *string
	n         *int
	rollBase  *int64
	oracle    *string
}

func addSurgeOverrides(fs *flag.FlagSet) surgeOverrides {
	return surgeOverrides{
		targets:   fs.String("targets", "", "comma-separated base URLs (overrides the scenario)"),
		releaseAt: fs.Int64("release-at", 0, "release time, Unix ms (overrides the scenario)"),
		peak:      fs.Float64("peak", 0, "peak arrivals per second (overrides the scenario)"),
		seed:      fs.Uint64("gen-seed", 0, "generator seed (overrides the scenario)"),
		name:      fs.String("name", "", "run name (overrides the scenario)"),
		n:         fs.Int("n", 0, "number of students (overrides dataset.n)"),
		rollBase:  fs.Int64("roll-base", 0, "first roll number (overrides dataset.roll_base)"),
		oracle:    fs.String("oracle", "", "dataset | roll_only (use roll_only against real data)"),
	}
}

func (o surgeOverrides) apply(sc *surge.Scenario) {
	if *o.targets != "" {
		sc.Targets = strings.Split(*o.targets, ",")
	}
	if *o.releaseAt != 0 {
		sc.ReleaseAtUnixMs = *o.releaseAt
	}
	if *o.peak != 0 {
		sc.Surge.PeakUsersPerS = *o.peak
	}
	if *o.seed != 0 {
		sc.Generator.Seed = *o.seed
	}
	if *o.name != "" {
		sc.Name = *o.name
	}
	if *o.n != 0 {
		sc.Dataset.N = *o.n
	}
	if *o.rollBase != 0 {
		sc.Dataset.RollBase = *o.rollBase
	}
	if *o.oracle != "" {
		sc.Oracle = *o.oracle
	}
}

func loadScenario(path string) (surge.Scenario, error) {
	if path == "" {
		return surge.Default(), nil
	}
	return surge.Load(path)
}

func runSurge(args []string) error {
	fs := flag.NewFlagSet("surge", flag.ExitOnError)
	scPath := fs.String("scenario", "", "scenario YAML (default: built-in defaults)")
	out := fs.String("out", "out", "output directory")
	ov := addSurgeOverrides(fs)
	if err := parse(fs, args); err != nil {
		return err
	}
	sc, err := loadScenario(*scPath)
	if err != nil {
		return err
	}
	ov.apply(&sc)
	ctx, stop := signalContext()
	defer stop()
	g, err := surge.New(sc, *out, log.Printf)
	if err != nil {
		return err
	}
	s, err := g.Run(ctx)
	if err != nil {
		return err
	}
	printSummary(s)
	return nil
}

func printSummary(s surge.Summary) {
	fmt.Printf("users=%d dropped=%d requests=%d amplification=%.2f served_ok=%.4f\n",
		s.Users, s.DroppedUsers, s.Requests, s.Amplification, s.UserServedOK)
	for k, v := range s.UserSuccessWithin {
		fmt.Printf("  success within %s: %.4f\n", k, v)
	}
	fmt.Printf("  wrong=%d stale=%d missing=%d soft=%d\n", s.WrongRequests, s.StaleRequests, s.MissingRequests, s.SoftFailures)
	fmt.Printf("  latency(all) p50=%.1fms p99=%.1fms; time-to-result p50=%.0fms p95=%.0fms\n",
		s.LatencyAllMs.P50, s.LatencyAllMs.P99, s.TimeToResultMs.P50, s.TimeToResultMs.P95)
	fmt.Printf("  outcomes: %v\n", s.RequestsByOutcome)
	if s.Generator.Saturated {
		fmt.Printf("  WARNING: load generator saturated (max %.2f of %d cores); discard this run\n",
			s.Generator.CPUMaxCores, s.Generator.GoMaxProcs)
	}
}

// Calibration is written to capacity.json.
type Calibration struct {
	Target        string  `json:"target"`
	DeadlineS     float64 `json:"deadline_s"`
	Threshold     float64 `json:"threshold"`
	CapacityUsers float64 `json:"capacity_users_per_s"`
	// GeneratorLimited means the generator saturated before the design did,
	// so the capacity is a lower bound.
	GeneratorLimited bool        `json:"generator_limited"`
	Steps            []CalibStep `json:"steps"`
}

// CalibStep is one constant-rate step.
type CalibStep struct {
	Rate          float64 `json:"rate"`
	SuccessWithin float64 `json:"success_within"`
	LatencyP99Ms  float64 `json:"latency_p99_ms"`
	Saturated     bool    `json:"generator_saturated"`
	Pass          bool    `json:"pass"`
}

func runCalibrate(args []string) error {
	fs := flag.NewFlagSet("calibrate", flag.ExitOnError)
	scPath := fs.String("scenario", "", "base scenario YAML (dataset, keys)")
	out := fs.String("out", "calibration", "output directory")
	start := fs.Float64("start", 50, "first rate (users/s)")
	step := fs.Float64("step", 50, "rate increment")
	growth := fs.Float64("growth", 1.0, "multiply the increment by this after each passing step")
	maxRate := fs.Float64("max", 50_000, "stop at this rate")
	stepS := fs.Float64("step-s", 20, "seconds per step")
	pauseS := fs.Float64("pause-s", 5, "seconds between steps")
	deadline := fs.Float64("deadline", 2, "deadline in seconds")
	threshold := fs.Float64("threshold", 0.99, "share of users that must get a correct result within the deadline")
	refine := fs.Int("refine", 3, "bisection steps after the first failure")
	ov := addSurgeOverrides(fs)
	if err := parse(fs, args); err != nil {
		return err
	}
	base, err := loadScenario(*scPath)
	if err != nil {
		return err
	}
	ov.apply(&base)
	// Calibration measures raw capacity: no retries, no repeat views, results
	// already released, constant arrival rate.
	base.Surge.Shape = "constant"
	base.Surge.PostReleaseS = *stepS
	base.ReleaseAtUnixMs = 0
	base.ReleaseInS = 0
	base.Users.RetryProb, base.Users.ImpatientRetryProb, base.Users.RepeatViewProb = 0, 0, 0
	base.Users.PatienceS = surge.Range{10, 10}
	base.Keys.TypoRate = 0
	base.DeadlinesS = []float64{*deadline}
	base.Generator.DrainS = 15
	key := strconv.FormatFloat(*deadline, 'f', -1, 64) + "s"

	ctx, stop := signalContext()
	defer stop()
	cal := Calibration{Target: strings.Join(base.Targets, ","), DeadlineS: *deadline, Threshold: *threshold}
	// Phase 1 grows the rate until two steps fail. Phase 2 bisects between the
	// last passing and the first failing rate.
	runStep := func(rate float64) (CalibStep, error) {
		sc := base
		sc.Name = fmt.Sprintf("calibrate-%g", rate)
		sc.Surge.PeakUsersPerS = rate
		sc.Generator.Seed = base.Generator.Seed + uint64(len(cal.Steps))
		g, err := surge.New(sc, filepath.Join(*out, fmt.Sprintf("step-%03d", len(cal.Steps))), nil)
		if err != nil {
			return CalibStep{}, err
		}
		s, err := g.Run(ctx)
		if err != nil {
			return CalibStep{}, err
		}
		st := CalibStep{Rate: rate, SuccessWithin: s.UserSuccessWithin[key], LatencyP99Ms: s.LatencyAllMs.P99,
			Saturated: s.Generator.Saturated}
		st.Pass = st.SuccessWithin >= *threshold && !st.Saturated
		cal.Steps = append(cal.Steps, st)
		log.Printf("rate %.0f/s: success within %gs = %.4f, p99 = %.0f ms, pass=%v", rate, *deadline, st.SuccessWithin, st.LatencyP99Ms, st.Pass)
		time.Sleep(time.Duration(*pauseS * float64(time.Second)))
		return st, nil
	}
	fails, firstFail := 0, 0.0
	inc := *step
	for rate := *start; rate <= *maxRate && fails < 2; rate += inc {
		st, err := runStep(rate)
		if err != nil {
			return err
		}
		if st.Saturated {
			log.Printf("load generator saturated at %.0f/s; capacity is at least %.0f/s", rate, cal.CapacityUsers)
			cal.GeneratorLimited = true
			break
		}
		if st.Pass {
			fails = 0
			cal.CapacityUsers = rate
			inc *= *growth
		} else {
			if fails == 0 {
				firstFail = rate
			}
			fails++
		}
	}
	lo, hi := cal.CapacityUsers, firstFail
	for i := 0; i < *refine && hi > 0 && hi-lo > 0.05*lo; i++ {
		mid := (lo + hi) / 2
		st, err := runStep(mid)
		if err != nil {
			return err
		}
		if st.Pass {
			lo = mid
			cal.CapacityUsers = mid
		} else {
			hi = mid
		}
	}
	log.Printf("capacity: %.0f users/s", cal.CapacityUsers)
	return writeReport(filepath.Join(*out, "capacity.json"), cal)
}
