// Package wroom implements a virtual waiting room: an admission layer that
// lets a safe number of users per second through to the backend and holds
// the rest in a queue, telling them their position.
//
// Two queue policies are supported:
//   - fifo:   users are admitted in arrival order.
//   - random: everyone who arrived before release time is shuffled at release
//     (a pre-queue lottery, as offered by commercial waiting rooms); later
//     arrivals are admitted in arrival order after them.
//
// Two ticket implementations are supported, which differ in what happens when
// a user refreshes the page:
//   - naive: the ticket lives only in the page (returned in the body and sent
//     back by the page's polling script). A manual refresh loses it and the
//     user rejoins at the back.
//   - token: the ticket is also stored in a signed cookie, so a refresh keeps
//     the user's place.
package wroom

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	mrand "math/rand/v2"
	"net/http"
	"net/http/httputil"
	"net/url"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/k144u/nocrashing/resultbench/internal/metrics"
)

// Policy names.
const (
	PolicyFIFO   = "fifo"
	PolicyRandom = "random"
	ModeNaive    = "naive"
	ModeToken    = "token"
)

// CookieName and HeaderName carry the ticket in token and naive mode.
const (
	CookieName = "rbq"
	HeaderName = "X-Queue-Ticket"
)

// Config controls the room.
type Config struct {
	Policy       string
	Mode         string
	ReleaseAt    time.Time     // zero means already released
	AdmitRate    float64       // users admitted per second
	Burst        float64       // most admissions that can happen at once
	MaxActive    int           // most users admitted at the same time (0 = no limit)
	SessionTTL   time.Duration // how long an admitted user may reach the backend
	AbandonAfter time.Duration // a queued user not seen for this long is skipped
	PollInterval time.Duration // suggested time between status checks
	Secret       []byte        // HMAC key for token mode
	Seed         uint64        // for the random policy
}

const (
	stateQueued = iota
	stateAdmitted
)

type ticket struct {
	id       string
	rank     int64
	state    int
	lastSeen time.Time
	expires  time.Time
}

// Room is the waiting room state machine. It is safe for concurrent use.
type Room struct {
	cfg Config
	m   *metrics.Registry
	rng *mrand.Rand

	mu         sync.Mutex
	tickets    map[string]*ticket
	preRelease []*ticket
	queue      []*ticket // ordered by rank; queue[head:] are waiting
	head       int
	nextRank   int64
	released   bool
	tokens     float64
	lastTick   time.Time
	admitted   []*ticket // in admission order; expiries are in the same order
	active     int
}

// New creates a room. Call Run (or Tick) to make admissions happen.
func New(cfg Config) *Room {
	if cfg.Policy == "" {
		cfg.Policy = PolicyFIFO
	}
	if cfg.Mode == "" {
		cfg.Mode = ModeToken
	}
	if cfg.Burst <= 0 {
		cfg.Burst = max(1, cfg.AdmitRate)
	}
	if cfg.SessionTTL == 0 {
		cfg.SessionTTL = 60 * time.Second
	}
	if cfg.AbandonAfter == 0 {
		cfg.AbandonAfter = 30 * time.Second
	}
	if cfg.PollInterval == 0 {
		cfg.PollInterval = 5 * time.Second
	}
	r := &Room{
		cfg:     cfg,
		m:       metrics.New("wroom"),
		rng:     mrand.New(mrand.NewPCG(cfg.Seed, 0x5EED)),
		tickets: map[string]*ticket{},
	}
	if cfg.ReleaseAt.IsZero() {
		r.released, r.lastTick = true, time.Now()
	}
	r.m.GaugeFunc("queue_length", func() int64 {
		r.mu.Lock()
		defer r.mu.Unlock()
		return int64(len(r.queue) - r.head + len(r.preRelease))
	})
	r.m.GaugeFunc("active_sessions", func() int64 { r.mu.Lock(); defer r.mu.Unlock(); return int64(r.active) })
	return r
}

// Metrics exposes the registry.
func (r *Room) Metrics() *metrics.Registry { return r.m }

// Run ticks every interval until stop is closed.
func (r *Room) Run(interval time.Duration, stop <-chan struct{}) {
	t := time.NewTicker(interval)
	defer t.Stop()
	for {
		select {
		case <-stop:
			return
		case now := <-t.C:
			r.Tick(now)
		}
	}
}

// Tick performs release, session expiry and admissions up to now.
func (r *Room) Tick(now time.Time) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if !r.released {
		if !r.cfg.ReleaseAt.IsZero() && now.Before(r.cfg.ReleaseAt) {
			return
		}
		r.release(now)
	}
	r.expireSessions(now)
	dt := now.Sub(r.lastTick).Seconds()
	r.lastTick = now
	r.tokens = min(r.cfg.Burst, r.tokens+r.cfg.AdmitRate*dt)
	for r.tokens >= 1 && r.head < len(r.queue) && (r.cfg.MaxActive == 0 || r.active < r.cfg.MaxActive) {
		t := r.queue[r.head]
		r.queue[r.head] = nil
		r.head++
		if t.state != stateQueued {
			continue
		}
		if now.Sub(t.lastSeen) > r.cfg.AbandonAfter {
			delete(r.tickets, t.id)
			r.m.Counter("abandoned").Inc()
			continue
		}
		r.admit(t, now)
		r.tokens--
	}
	if r.head > 4096 && r.head > len(r.queue)/2 {
		r.queue = append([]*ticket(nil), r.queue[r.head:]...)
		r.head = 0
	}
}

func (r *Room) release(now time.Time) {
	r.released = true
	r.lastTick = now
	pre := r.preRelease
	r.preRelease = nil
	if r.cfg.Policy == PolicyRandom {
		r.rng.Shuffle(len(pre), func(i, j int) { pre[i], pre[j] = pre[j], pre[i] })
		for i, t := range pre {
			t.rank = int64(i)
		}
		r.nextRank = int64(len(pre))
	} else {
		sort.Slice(pre, func(i, j int) bool { return pre[i].rank < pre[j].rank })
	}
	r.queue = append(r.queue, pre...)
	r.m.Counter("prerelease_tickets").Add(int64(len(pre)))
}

func (r *Room) expireSessions(now time.Time) {
	n := 0
	for n < len(r.admitted) && !now.Before(r.admitted[n].expires) {
		delete(r.tickets, r.admitted[n].id)
		r.admitted[n] = nil
		n++
	}
	if n > 0 {
		r.admitted = r.admitted[n:]
		r.active -= n
	}
}

func (r *Room) admit(t *ticket, now time.Time) {
	t.state = stateAdmitted
	t.expires = now.Add(r.cfg.SessionTTL)
	r.admitted = append(r.admitted, t)
	r.active++
	r.m.Counter("admitted").Inc()
}

// Decision is what the room decided for one request.
type Decision struct {
	Admit    bool
	TicketID string
	Position int64 // -1 before release under the random policy
	New      bool  // a ticket was created for this request
}

// Arrive handles one request that carries ticket id (possibly empty).
func (r *Room) Arrive(id string, now time.Time) Decision {
	r.mu.Lock()
	defer r.mu.Unlock()
	if t, ok := r.tickets[id]; ok && id != "" {
		t.lastSeen = now
		switch {
		case t.state == stateAdmitted && now.Before(t.expires):
			return Decision{Admit: true, TicketID: t.id}
		case t.state == stateQueued:
			return Decision{TicketID: t.id, Position: r.position(t)}
		}
	}
	t := &ticket{id: newID(), lastSeen: now}
	r.tickets[t.id] = t
	r.m.Counter("tickets_created").Inc()
	if !r.released {
		if r.cfg.Policy == PolicyFIFO {
			t.rank = r.nextRank
			r.nextRank++
		}
		r.preRelease = append(r.preRelease, t)
		return Decision{TicketID: t.id, Position: r.position(t), New: true}
	}
	// Fast path: nobody is waiting and there is spare capacity right now.
	if r.head == len(r.queue) && r.tokens >= 1 && (r.cfg.MaxActive == 0 || r.active < r.cfg.MaxActive) {
		r.tokens--
		r.admit(t, now)
		r.m.Counter("fast_path_admits").Inc()
		return Decision{Admit: true, TicketID: t.id, New: true}
	}
	t.rank = r.nextRank
	r.nextRank++
	r.queue = append(r.queue, t)
	return Decision{TicketID: t.id, Position: r.position(t), New: true}
}

func (r *Room) position(t *ticket) int64 {
	if !r.released {
		if r.cfg.Policy == PolicyRandom {
			return -1
		}
		return t.rank
	}
	if r.head >= len(r.queue) {
		return 0
	}
	return max(0, t.rank-r.queue[r.head].rank)
}

func newID() string {
	var b [12]byte
	rand.Read(b[:])
	return hex.EncodeToString(b[:])
}

// Handler is the HTTP front of the room. Admitted requests are proxied to
// the backend unchanged.
type Handler struct {
	room    *Room
	proxy   *httputil.ReverseProxy
	backend *url.URL
}

// NewHandler builds the HTTP handler.
func NewHandler(room *Room, backend string) (*Handler, error) {
	u, err := url.Parse(backend)
	if err != nil {
		return nil, err
	}
	p := httputil.NewSingleHostReverseProxy(u)
	p.Transport = &http.Transport{
		MaxIdleConns:        4096,
		MaxIdleConnsPerHost: 4096,
		IdleConnTimeout:     90 * time.Second,
	}
	p.ErrorHandler = func(w http.ResponseWriter, _ *http.Request, _ error) {
		room.m.Counter("proxy_errors").Inc()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		w.Write([]byte(`{"error":"bad gateway"}`))
	}
	return &Handler{room: room, proxy: p, backend: u}, nil
}

// Routes returns the mux: /metrics and /stats belong to the room, everything
// else goes through admission.
func (h *Handler) Routes() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/metrics", h.room.m.ServeMetrics)
	mux.HandleFunc("/stats", h.room.m.ServeStats)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte("ok\n")) })
	mux.Handle("/", h)
	return mux
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	id := h.ticketFrom(req)
	d := h.room.Arrive(id, time.Now())
	if h.room.cfg.Mode == ModeToken && d.New {
		http.SetCookie(w, &http.Cookie{Name: CookieName, Value: h.sign(d.TicketID), Path: "/", HttpOnly: true})
	}
	if d.Admit {
		h.room.m.Counter("proxied").Inc()
		h.proxy.ServeHTTP(w, req)
		return
	}
	h.room.m.Counter("queued_responses").Inc()
	jitter := 0.8 + 0.4*mrand.Float64()
	retry := time.Duration(float64(h.room.cfg.PollInterval) * jitter)
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	fmt.Fprintf(w, `{"status":"queued","ticket":%q,"position":%d,"retry_after_ms":%d}`, d.TicketID, d.Position, retry.Milliseconds())
}

func (h *Handler) ticketFrom(req *http.Request) string {
	if h.room.cfg.Mode == ModeNaive {
		return req.Header.Get(HeaderName)
	}
	c, err := req.Cookie(CookieName)
	if err != nil {
		return ""
	}
	id, sig, ok := strings.Cut(c.Value, ".")
	if !ok || !hmac.Equal([]byte(sig), []byte(h.mac(id))) {
		h.room.m.Counter("bad_tokens").Inc()
		return ""
	}
	return id
}

func (h *Handler) sign(id string) string { return id + "." + h.mac(id) }

func (h *Handler) mac(id string) string {
	m := hmac.New(sha256.New, h.room.cfg.Secret)
	m.Write([]byte(id))
	return hex.EncodeToString(m.Sum(nil)[:16])
}
