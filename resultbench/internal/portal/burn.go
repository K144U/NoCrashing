package portal

import (
	"crypto/sha256"
	"runtime"
	"syscall"
	"time"
)

// PageCost models the CPU a typical portal spends building one result page
// on top of the database query: framework overhead, session handling and
// HTML rendering. Real portal stacks (PHP, ASP.NET, Java) spend milliseconds
// here; this Go server spends microseconds, which would make the
// database-backed design unrealistically cheap.
//
// The cost is applied wherever a page is built from the database: every
// request in design A, and every cache miss in design B. Pre-computed designs
// store the finished page and never pay it. The value is an explicit
// assumption of the study and should be varied (0 is allowed).
type PageCost struct {
	iters int
}

const rusageThread = 1 // RUSAGE_THREAD on Linux

func threadCPU() time.Duration {
	var ru syscall.Rusage
	if err := syscall.Getrusage(rusageThread, &ru); err != nil {
		return 0
	}
	return time.Duration(ru.Utime.Nano() + ru.Stime.Nano())
}

var burnBuf = make([]byte, 1024)

func burnOnce() { sha256.Sum256(burnBuf) }

// NewPageCost converts a CPU duration into a fixed amount of work, measured
// in thread CPU time so that container CPU limits during start-up do not
// distort it. The work is fixed, so under CPU throttling it takes longer in
// wall time, as real work would.
func NewPageCost(cost time.Duration) PageCost {
	if cost <= 0 {
		return PageCost{}
	}
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	start := threadCPU()
	n := 0
	var used time.Duration
	for used < 50*time.Millisecond {
		for i := 0; i < 100; i++ {
			burnOnce()
		}
		n += 100
		used = threadCPU() - start
		if used == 0 && n > 10_000_000 {
			break // no thread clock; give up measuring
		}
	}
	if used <= 0 {
		return PageCost{iters: int(cost / time.Microsecond)}
	}
	return PageCost{iters: int(float64(n) * float64(cost) / float64(used))}
}

// Spend performs the work for one page.
func (p PageCost) Spend() {
	for i := 0; i < p.iters; i++ {
		burnOnce()
	}
}

// Iterations reports the calibrated amount of work.
func (p PageCost) Iterations() int { return p.iters }
