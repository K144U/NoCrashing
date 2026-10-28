package wroom

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestFIFOOrderAndRate(t *testing.T) {
	t0 := time.Unix(1_000_000, 0)
	r := New(Config{Policy: PolicyFIFO, ReleaseAt: t0, AdmitRate: 10, Burst: 1, AbandonAfter: time.Hour})
	var ids []string
	for i := 0; i < 5; i++ {
		d := r.Arrive("", t0.Add(-time.Duration(5-i)*time.Second))
		if d.Admit {
			t.Fatal("admitted before release")
		}
		ids = append(ids, d.TicketID)
	}
	if d := r.Arrive(ids[3], t0.Add(-time.Second)); d.Position != 3 {
		t.Fatalf("pre-release FIFO position = %d, want 3", d.Position)
	}
	r.Tick(t0) // release, no tokens yet
	var order []int
	for step := 1; step <= 10 && len(order) < 5; step++ {
		now := t0.Add(time.Duration(step) * 100 * time.Millisecond)
		r.Tick(now)
		for i, id := range ids {
			d := r.Arrive(id, now)
			if d.Admit && !contains(order, i) {
				order = append(order, i)
			}
		}
	}
	for i := range order {
		if order[i] != i {
			t.Fatalf("FIFO admitted in order %v", order)
		}
	}
	if len(order) != 5 {
		t.Fatalf("admitted %d of 5 after 1s at 10/s", len(order))
	}
}

func contains(s []int, v int) bool {
	for _, x := range s {
		if x == v {
			return true
		}
	}
	return false
}

func TestRandomPolicyShufflesPreQueue(t *testing.T) {
	t0 := time.Unix(1_000_000, 0)
	r := New(Config{Policy: PolicyRandom, ReleaseAt: t0, AdmitRate: 1000, Burst: 1000, AbandonAfter: time.Hour, Seed: 3})
	const n = 200
	ids := make([]string, n)
	for i := range ids {
		ids[i] = r.Arrive("", t0.Add(-time.Minute+time.Duration(i)*time.Millisecond)).TicketID
		if p := r.Arrive(ids[i], t0.Add(-time.Second)).Position; p != -1 {
			t.Fatalf("random policy revealed position %d before release", p)
		}
	}
	r.Tick(t0)
	// Collect ranks: lower rank is admitted first.
	inversions := 0
	for i := 1; i < n; i++ {
		if r.tickets[ids[i]].rank < r.tickets[ids[i-1]].rank {
			inversions++
		}
	}
	if inversions < n/4 {
		t.Fatalf("pre-queue does not look shuffled (%d inversions)", inversions)
	}
	late := r.Arrive("", t0.Add(time.Millisecond))
	if late.Admit || r.tickets[late.TicketID].rank < n {
		t.Fatal("post-release arrival jumped ahead of the pre-queue")
	}
}

func TestAbandonedTicketsSkipped(t *testing.T) {
	t0 := time.Unix(1_000_000, 0)
	r := New(Config{ReleaseAt: t0, AdmitRate: 1, Burst: 1, AbandonAfter: 10 * time.Second})
	ghost := r.Arrive("", t0.Add(-time.Minute)).TicketID
	live := r.Arrive("", t0.Add(-time.Second)).TicketID
	r.Tick(t0)
	r.Arrive(live, t0.Add(500*time.Millisecond))
	r.Tick(t0.Add(time.Second))
	if !r.Arrive(live, t0.Add(time.Second)).Admit {
		t.Fatal("live user not admitted after ghost was skipped")
	}
	if r.Metrics().Snapshot()["abandoned"] != 1 {
		t.Fatal("ghost not counted as abandoned")
	}
	_ = ghost
}

func TestSessionExpiry(t *testing.T) {
	t0 := time.Unix(1_000_000, 0)
	r := New(Config{ReleaseAt: t0, AdmitRate: 100, Burst: 100, SessionTTL: 5 * time.Second, MaxActive: 1})
	r.Tick(t0)
	r.Tick(t0.Add(time.Second))
	a := r.Arrive("", t0.Add(time.Second))
	if !a.Admit {
		t.Fatal("first user should take the fast path")
	}
	b := r.Arrive("", t0.Add(time.Second))
	if b.Admit {
		t.Fatal("max-active not enforced")
	}
	r.Tick(t0.Add(7 * time.Second))
	if !r.Arrive(b.TicketID, t0.Add(7*time.Second)).Admit {
		t.Fatal("second user not admitted after first session expired")
	}
}

func TestHandlerTokenAndNaive(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte(`{"roll":1}`)) }))
	defer backend.Close()
	for _, mode := range []string{ModeToken, ModeNaive} {
		room := New(Config{Mode: mode, AdmitRate: 0.0001, Burst: 1, Secret: []byte("k")})
		room.Tick(time.Now())
		h, _ := NewHandler(room, backend.URL)
		srv := httptest.NewServer(h.Routes())
		// First request: fast path, admitted.
		resp, _ := http.Get(srv.URL + "/result?roll=1")
		resp.Body.Close()
		if resp.StatusCode != 200 {
			t.Fatalf("%s: status %d", mode, resp.StatusCode)
		}
		// Second user: no tokens left, queued.
		resp, _ = http.Get(srv.URL + "/result?roll=2")
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if !strings.Contains(string(body), `"status":"queued"`) {
			t.Fatalf("%s: expected queued, got %s", mode, body)
		}
		hasCookie := len(resp.Cookies()) > 0
		if hasCookie != (mode == ModeToken) {
			t.Fatalf("%s: cookie present = %v", mode, hasCookie)
		}
		srv.Close()
	}
}

func TestForgedTokenRejected(t *testing.T) {
	room := New(Config{Mode: ModeToken, AdmitRate: 1, Secret: []byte("k")})
	h, _ := NewHandler(room, "http://127.0.0.1:1")
	req := httptest.NewRequest("GET", "/result?roll=1", nil)
	req.AddCookie(&http.Cookie{Name: CookieName, Value: "abc.deadbeef"})
	if id := h.ticketFrom(req); id != "" {
		t.Fatal("forged token accepted")
	}
}
