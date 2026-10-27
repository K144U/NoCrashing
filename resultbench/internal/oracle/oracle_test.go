package oracle

import (
	"testing"

	"github.com/k144u/nocrashing/resultbench/internal/dataset"
)

func TestClassify(t *testing.T) {
	cfg := dataset.Default()
	cfg.N = 10_000
	o := Oracle{Cfg: cfg}
	corrIdx := -1
	for i := 0; i < cfg.N; i++ {
		if cfg.IsCorrected(i) {
			corrIdx = i
			break
		}
	}
	if corrIdx < 0 {
		t.Fatal("no corrected student in sample")
	}
	roll := cfg.Roll(3)
	croll := cfg.Roll(corrIdx)
	other := dataset.JSON(cfg.Original(4))
	tampered := cfg.Original(3)
	tampered.Marks[0].Marks++
	dataset.Finalize(&tampered)

	cases := []struct {
		name      string
		code      int
		body      []byte
		roll      int64
		published bool
		want      Outcome
	}{
		{"correct", 200, dataset.JSON(cfg.Original(3)), roll, false, Correct},
		{"correct after corrections, uncorrected student", 200, dataset.JSON(cfg.Original(3)), roll, true, Correct},
		{"corrected student before publication", 200, dataset.JSON(cfg.Original(corrIdx)), croll, false, Correct},
		{"stale after publication", 200, dataset.JSON(cfg.Original(corrIdx)), croll, true, Stale},
		{"new version after publication", 200, dataset.JSON(cfg.Corrected(corrIdx)), croll, true, Correct},
		{"new version too early", 200, dataset.JSON(cfg.Corrected(corrIdx)), croll, false, Ahead},
		{"another student's result", 200, other, roll, false, Wrong},
		{"tampered marks", 200, dataset.JSON(tampered), roll, false, Wrong},
		{"html error page with 200", 200, []byte("<html>Service busy</html>"), roll, false, SoftFailure},
		{"empty 200", 200, nil, roll, false, SoftFailure},
		{"missing", 404, nil, roll, false, Missing},
		{"typo not found", 404, nil, cfg.RollBase + int64(cfg.N) + 5, false, CorrectNotFound},
		{"not released", 425, []byte(`{"status":"not_released"}`), roll, false, NotReleased},
		{"queued", 200, []byte(`{"status":"queued","ticket":"abc","position":10,"retry_after_ms":5000}`), roll, false, Queued},
		{"shed", 503, nil, roll, false, Rejected},
		{"rate limited", 429, nil, roll, false, Rejected},
		{"bad gateway", 502, nil, roll, false, ServerError},
		{"forbidden", 403, nil, roll, false, ClientError},
	}
	for _, c := range cases {
		got, _ := o.Classify(c.code, c.body, c.roll, c.published)
		if got != c.want {
			t.Errorf("%s: got %s, want %s", c.name, got, c.want)
		}
	}
	_, st := o.Classify(200, []byte(`{"status":"queued","ticket":"abc","position":10,"retry_after_ms":5000}`), roll, false)
	if st == nil || st.Ticket != "abc" || st.RetryAfterMs != 5000 {
		t.Fatalf("queued status not parsed: %+v", st)
	}
}
