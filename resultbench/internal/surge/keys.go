package surge

import (
	"math/bits"
	"math/rand/v2"
)

// permutation is a keyed bijection on [0, n) built from a small Feistel
// network with cycle walking. It lets the generator hand each arriving
// student a different roll number without storing a shuffled array.
type permutation struct {
	n    uint64
	half uint
	mask uint64
	keys [4]uint64
}

func newPermutation(n uint64, seed uint64) permutation {
	b := uint(bits.Len64(n - 1))
	if b < 2 {
		b = 2
	}
	if b%2 == 1 {
		b++
	}
	p := permutation{n: n, half: b / 2, mask: (1 << (b / 2)) - 1}
	r := rand.New(rand.NewPCG(seed, 0xFE15))
	for i := range p.keys {
		p.keys[i] = r.Uint64()
	}
	return p
}

func (p permutation) round(x, k uint64) uint64 {
	x ^= k
	x *= 0x9E3779B97F4A7C15
	x ^= x >> 29
	return x & p.mask
}

func (p permutation) encrypt(x uint64) uint64 {
	l, r := x>>p.half, x&p.mask
	for _, k := range p.keys {
		l, r = r, l^p.round(r, k)
	}
	return l<<p.half | r
}

// At returns the i-th element of the permutation (i < n).
func (p permutation) At(i uint64) uint64 {
	x := i
	for {
		x = p.encrypt(x)
		if x < p.n {
			return x
		}
	}
}

// keyChooser picks the roll number for each arriving student.
type keyChooser struct {
	spec   KeySpec
	n      int
	base   int64
	perm   permutation
	rng    *rand.Rand
	zipf   *rand.Zipf
	served uint64
}

func newKeyChooser(spec KeySpec, n int, base int64, seed uint64) *keyChooser {
	k := &keyChooser{spec: spec, n: n, base: base, perm: newPermutation(uint64(n), seed),
		rng: rand.New(rand.NewPCG(seed, 0xC0FFEE))}
	if spec.Dist == "zipf" {
		k.zipf = rand.NewZipf(k.rng, spec.ZipfS, 1, uint64(n-1))
	}
	return k
}

// Next returns a roll number. It is not safe for concurrent use.
func (k *keyChooser) Next() int64 {
	if k.spec.TypoRate > 0 && k.rng.Float64() < k.spec.TypoRate {
		// A typo: a roll number just outside the valid range.
		return k.base + int64(k.n) + int64(k.rng.IntN(1_000_000))
	}
	var idx uint64
	if k.zipf != nil {
		idx = k.perm.At(k.zipf.Uint64())
	} else {
		idx = k.perm.At(k.served % uint64(k.n))
		k.served++
	}
	return k.base + int64(idx)
}
