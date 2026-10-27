package dataset

import (
	"encoding/json"
	"testing"
)

func small() Config {
	c := Default()
	c.N = 20_000
	return c
}

func TestDeterministic(t *testing.T) {
	c := small()
	for _, i := range []int{0, 1, 999, c.N - 1} {
		a, b := c.Original(i), c.Original(i)
		if Fingerprint(a) != Fingerprint(b) {
			t.Fatalf("student %d differs between calls", i)
		}
	}
	d := c
	d.Seed++
	if Fingerprint(c.Original(5)) == Fingerprint(d.Original(5)) {
		t.Fatal("different seeds produced the same record")
	}
}

func TestRules(t *testing.T) {
	c := small()
	counts := map[string]int{}
	for i := 0; i < c.N; i++ {
		r := c.Original(i)
		total, failed := 0, 0
		for _, m := range r.Marks {
			if m.Marks < 0 || m.Marks > 100 {
				t.Fatalf("marks out of range: %+v", r)
			}
			total += m.Marks
			if m.Marks < PassMark {
				failed++
			}
		}
		if total != r.Total {
			t.Fatalf("total mismatch for %d", r.Roll)
		}
		if (failed == 0) != (r.Result == "PASS") {
			t.Fatalf("result rule broken: %+v", r)
		}
		counts[r.Result]++
	}
	// The generator should produce a plausible mix, mostly passes.
	if p := float64(counts["PASS"]) / float64(c.N); p < 0.6 || p > 0.98 {
		t.Fatalf("implausible pass rate %.2f (%v)", p, counts)
	}
}

func TestCorrections(t *testing.T) {
	c := small()
	n := 0
	for i := 0; i < c.N; i++ {
		if !c.IsCorrected(i) {
			if Fingerprint(c.Current(i, true)) != Fingerprint(c.Original(i)) {
				t.Fatal("uncorrected student changed")
			}
			continue
		}
		n++
		o, k := c.Original(i), c.Corrected(i)
		if k.Version != 2 || k.Total < o.Total {
			t.Fatalf("bad correction: version %d, total %d -> %d", k.Version, o.Total, k.Total)
		}
		if Fingerprint(o) == Fingerprint(k) {
			t.Fatal("corrected record has the same fingerprint")
		}
	}
	if share := float64(n) / float64(c.N); share < 0.005 || share > 0.015 {
		t.Fatalf("correction share %.4f, want about 0.01", share)
	}
}

func TestFingerprintIgnoresFormatting(t *testing.T) {
	c := small()
	r := c.Original(7)
	var back Record
	if err := json.Unmarshal(JSON(r), &back); err != nil {
		t.Fatal(err)
	}
	if Fingerprint(back) != Fingerprint(r) {
		t.Fatal("round trip changed fingerprint")
	}
}

func TestValid(t *testing.T) {
	c := small()
	if _, ok := c.Valid(c.RollBase - 1); ok {
		t.Fatal("roll below range accepted")
	}
	if i, ok := c.Valid(c.Roll(c.N - 1)); !ok || i != c.N-1 {
		t.Fatal("last roll rejected")
	}
	if _, ok := c.Valid(c.Roll(c.N)); ok {
		t.Fatal("roll above range accepted")
	}
}
