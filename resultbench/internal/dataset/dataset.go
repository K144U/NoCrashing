// Package dataset generates the synthetic result data used by every design.
//
// Every student record is a pure function of (seed, index), so the load
// generator can recompute the expected answer for any roll number without
// loading a ground-truth file. This is what lets the correctness oracle scale
// to millions of students.
package dataset

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"hash/fnv"
)

// Subject is one paper on the marksheet.
type Subject struct {
	Code string `json:"code"`
	Name string `json:"name"`
}

// Subjects is the fixed list of papers every student takes.
var Subjects = []Subject{
	{"HIN", "Hindi"},
	{"ENG", "English"},
	{"MAT", "Mathematics"},
	{"SCI", "Science"},
	{"SST", "Social Science"},
	{"CSC", "Computer Science"},
}

// PassMark is the minimum marks per subject.
const PassMark = 33

// Config identifies a dataset. Two runs with the same Config see identical data.
type Config struct {
	Seed     uint64
	N        int   // number of students
	RollBase int64 // roll number of student index 0
	// CorrectionPerMille is how many students in 1000 get a revised result
	// (re-totalling) after release.
	CorrectionPerMille int
	NumSchools         int
}

// Default returns the configuration used in the thesis unless stated otherwise.
func Default() Config {
	return Config{Seed: 42, N: 1_000_000, RollBase: 2710000000, CorrectionPerMille: 10, NumSchools: 5000}
}

// Mark is one subject's marks.
type Mark struct {
	Code  string `json:"code"`
	Name  string `json:"name"`
	Marks int    `json:"marks"`
}

// Record is the published result for one student. Its JSON form is the API
// response body for GET /result?roll=<roll>.
type Record struct {
	Roll       int64   `json:"roll"`
	Name       string  `json:"name"`
	FatherName string  `json:"father_name"`
	SchoolCode int     `json:"school_code"`
	SchoolName string  `json:"school_name"`
	District   string  `json:"district"`
	Marks      []Mark  `json:"marks"`
	Total      int     `json:"total"`
	MaxTotal   int     `json:"max_total"`
	Percentage float64 `json:"percentage"`
	Division   string  `json:"division"`
	Result     string  `json:"result"`
	Version    int     `json:"version"`
}

// School describes one school.
type School struct {
	Code     int
	Name     string
	District string
}

// splitmix64 is a small, fast, well-mixed PRNG step.
func splitmix64(x uint64) uint64 {
	x += 0x9E3779B97F4A7C15
	x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9
	x = (x ^ (x >> 27)) * 0x94D049BB133111EB
	return x ^ (x >> 31)
}

// rng is a deterministic stream derived from a seed.
type rng struct{ s uint64 }

func newRNG(parts ...uint64) *rng {
	s := uint64(0x5EED)
	for _, p := range parts {
		s = splitmix64(s ^ p)
	}
	return &rng{s: s}
}

func (r *rng) next() uint64 { r.s = splitmix64(r.s); return r.s }

func (r *rng) intn(n int) int { return int(r.next() % uint64(n)) }

// float returns a value in [0,1).
func (r *rng) float() float64 { return float64(r.next()>>11) / (1 << 53) }

// normal returns an approximately normal value (Irwin-Hall with 12 terms).
func (r *rng) normal(mean, sd float64) float64 {
	sum := 0.0
	for i := 0; i < 12; i++ {
		sum += r.float()
	}
	return mean + (sum-6)*sd
}

const (
	streamStudent    = 1
	streamCorrection = 2
	streamSchool     = 3
)

// Valid reports whether roll belongs to the dataset, and its index.
func (c Config) Valid(roll int64) (int, bool) {
	idx := roll - c.RollBase
	if idx < 0 || idx >= int64(c.N) {
		return 0, false
	}
	return int(idx), true
}

// Roll returns the roll number of student index i.
func (c Config) Roll(i int) int64 { return c.RollBase + int64(i) }

// SchoolByCode returns the school with the given code.
func (c Config) SchoolByCode(code int) School {
	r := newRNG(c.Seed, streamSchool, uint64(code))
	district := districts[r.intn(len(districts))]
	kind := schoolKinds[r.intn(len(schoolKinds))]
	return School{Code: code, Name: fmt.Sprintf("%s No. %d, %s", kind, 1+r.intn(40), district), District: district}
}

// Original returns the first published version of student i's result.
func (c Config) Original(i int) Record {
	r := newRNG(c.Seed, streamStudent, uint64(i))
	first := firstNames[r.intn(len(firstNames))]
	last := surnames[r.intn(len(surnames))]
	father := firstNames[r.intn(len(firstNames))] + " " + last
	school := c.SchoolByCode(1000 + r.intn(c.NumSchools))
	// A per-student ability shifts all subjects together, as in real marks.
	ability := r.normal(0, 12)
	marks := make([]Mark, len(Subjects))
	for k, s := range Subjects {
		m := int(r.normal(60+ability, 14) + 0.5)
		marks[k] = Mark{Code: s.Code, Name: s.Name, Marks: clamp(m, 0, 100)}
	}
	rec := Record{
		Roll:       c.Roll(i),
		Name:       first + " " + last,
		FatherName: father,
		SchoolCode: school.Code,
		SchoolName: school.Name,
		District:   school.District,
		Marks:      marks,
		Version:    1,
	}
	Finalize(&rec)
	return rec
}

// IsCorrected reports whether student i receives a revised result.
func (c Config) IsCorrected(i int) bool {
	if c.CorrectionPerMille <= 0 {
		return false
	}
	r := newRNG(c.Seed, streamCorrection, uint64(i))
	return r.intn(1000) < c.CorrectionPerMille
}

// Corrected returns the revised (version 2) result for student i. It is only
// meaningful when IsCorrected(i) is true. Re-totalling usually raises marks in
// one subject by a few points.
func (c Config) Corrected(i int) Record {
	rec := c.Original(i)
	r := newRNG(c.Seed, streamCorrection, uint64(i), 7)
	k := r.intn(len(rec.Marks))
	rec.Marks[k].Marks = clamp(rec.Marks[k].Marks+1+r.intn(10), 0, 100)
	rec.Version = 2
	Finalize(&rec)
	return rec
}

// Current returns the record that should be served at a moment when
// corrections have (published=true) or have not been published.
func (c Config) Current(i int, published bool) Record {
	if published && c.IsCorrected(i) {
		return c.Corrected(i)
	}
	return c.Original(i)
}

// Finalize recomputes the derived fields (total, percentage, division,
// result) from the subject marks. Portals that compute results at request
// time call this too, so the rules live in exactly one place.
func Finalize(rec *Record) {
	total, failed := 0, 0
	for _, m := range rec.Marks {
		total += m.Marks
		if m.Marks < PassMark {
			failed++
		}
	}
	rec.Total = total
	rec.MaxTotal = 100 * len(rec.Marks)
	pct := float64(total) * 100 / float64(rec.MaxTotal)
	rec.Percentage = float64(int(pct*100+0.5)) / 100
	switch {
	case failed >= 2:
		rec.Result, rec.Division = "FAIL", "-"
	case failed == 1:
		rec.Result, rec.Division = "COMPARTMENT", "-"
	default:
		rec.Result = "PASS"
		switch {
		case pct >= 60:
			rec.Division = "FIRST"
		case pct >= 45:
			rec.Division = "SECOND"
		default:
			rec.Division = "THIRD"
		}
	}
}

// Fingerprint is a hash over the fields a student cares about. Two responses
// with the same fingerprint show the same result. Formatting differences
// between designs (field order, whitespace) do not change it.
func Fingerprint(rec Record) uint64 {
	h := fnv.New64a()
	var b [8]byte
	put := func(v int64) { binary.LittleEndian.PutUint64(b[:], uint64(v)); h.Write(b[:]) }
	put(rec.Roll)
	put(int64(rec.Version))
	put(int64(rec.Total))
	for _, m := range rec.Marks {
		h.Write([]byte(m.Code))
		put(int64(m.Marks))
	}
	h.Write([]byte(rec.Division))
	h.Write([]byte(rec.Result))
	h.Write([]byte(rec.Name))
	return h.Sum64()
}

// JSON returns the canonical response body for a record.
func JSON(rec Record) []byte {
	b, err := json.Marshal(rec)
	if err != nil {
		panic(err) // Record has no unmarshalable fields
	}
	return b
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

var firstNames = []string{
	"Aarav", "Aditi", "Akash", "Ananya", "Anjali", "Arjun", "Ayesha", "Deepak", "Divya", "Farhan",
	"Gaurav", "Harsh", "Isha", "Kavya", "Kiran", "Manish", "Meera", "Mohit", "Neha", "Nikhil",
	"Pooja", "Pradeep", "Priya", "Rahul", "Rajesh", "Riya", "Rohan", "Sakshi", "Sana", "Sandeep",
	"Shreya", "Simran", "Sunil", "Tanvi", "Uday", "Varun", "Vikas", "Yash", "Zoya", "Lakshmi",
}

var surnames = []string{
	"Agarwal", "Ahmed", "Bose", "Chauhan", "Das", "Dubey", "Gupta", "Iyer", "Jain", "Khan",
	"Kumar", "Mishra", "Nair", "Pandey", "Patel", "Pathak", "Rao", "Reddy", "Sharma", "Singh",
	"Srivastava", "Tiwari", "Verma", "Yadav", "Shukla", "Tripathi", "Saxena", "Menon", "Ghosh", "Kaur",
}

var districts = []string{
	"Lucknow", "Kanpur", "Varanasi", "Prayagraj", "Agra", "Meerut", "Gorakhpur", "Bareilly",
	"Aligarh", "Jhansi", "Moradabad", "Ayodhya", "Mathura", "Saharanpur", "Firozabad", "Etawah",
}

var schoolKinds = []string{
	"Government Inter College", "Rajkiya Balika Inter College", "Saraswati Vidya Mandir",
	"Kendriya Vidyalaya", "Public Inter College", "Adarsh Inter College",
}
