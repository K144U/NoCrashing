package surge

import (
	"math"
	"testing"
)

func TestPermutationIsBijection(t *testing.T) {
	for _, n := range []uint64{1, 2, 3, 10, 1000, 4097} {
		p := newPermutation(n, 7)
		seen := make([]bool, n)
		for i := uint64(0); i < n; i++ {
			v := p.At(i)
			if v >= n || seen[v] {
				t.Fatalf("n=%d: value %d repeated or out of range", n, v)
			}
			seen[v] = true
		}
	}
}

func TestUniformKeysAreDistinct(t *testing.T) {
	k := newKeyChooser(KeySpec{Dist: "uniform"}, 5000, 100, 1)
	seen := map[int64]bool{}
	for i := 0; i < 5000; i++ {
		r := k.Next()
		if seen[r] {
			t.Fatalf("roll %d repeated before population exhausted", r)
		}
		seen[r] = true
	}
}

func TestZipfKeysAreSkewed(t *testing.T) {
	k := newKeyChooser(KeySpec{Dist: "zipf", ZipfS: 1.2}, 100_000, 0, 1)
	counts := map[int64]int{}
	for i := 0; i < 50_000; i++ {
		counts[k.Next()]++
	}
	top := 0
	for _, c := range counts {
		top = max(top, c)
	}
	if top < 1000 {
		t.Fatalf("hottest key seen %d times; zipf not skewed", top)
	}
}

func TestTypos(t *testing.T) {
	k := newKeyChooser(KeySpec{Dist: "uniform", TypoRate: 0.1}, 1000, 0, 1)
	typos := 0
	for i := 0; i < 10_000; i++ {
		if k.Next() >= 1000 {
			typos++
		}
	}
	if typos < 800 || typos > 1200 {
		t.Fatalf("typos %d, want about 1000", typos)
	}
}

func TestSurgeCurve(t *testing.T) {
	s := Default().Surge
	if s.Rate(-s.PreReleaseS-1) != 0 || s.Rate(s.PostReleaseS+1) != 0 {
		t.Fatal("rate outside window")
	}
	if got := s.Rate(s.RiseS); math.Abs(got-s.PeakUsersPerS) > 1e-9 {
		t.Fatalf("rate at end of rise = %v, want peak", got)
	}
	if s.Rate(-1) >= s.Rate(s.RiseS) {
		t.Fatal("pre-release rate not below peak")
	}
	if s.Rate(s.RiseS+s.DecayTauS) >= s.Rate(s.RiseS+1) {
		t.Fatal("no decay")
	}
	c := s
	c.Shape = "constant"
	if c.Rate(-1) != 0 || c.Rate(10) != c.PeakUsersPerS {
		t.Fatal("constant shape wrong")
	}
	if e := c.ExpectedUsers(); math.Abs(e-c.PeakUsersPerS*c.PostReleaseS) > c.PeakUsersPerS {
		t.Fatalf("expected users %v", e)
	}
}

func TestDefaultValid(t *testing.T) {
	sc := Default()
	if err := sc.Validate(); err != nil {
		t.Fatal(err)
	}
	sc.Keys = KeySpec{Dist: "zipf", ZipfS: 1}
	if sc.Validate() == nil {
		t.Fatal("zipf_s=1 accepted")
	}
}
