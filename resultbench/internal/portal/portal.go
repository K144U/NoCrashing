// Package portal implements the application server for the database-backed
// (A), cache-aside (B0-B3) and pre-computed key-value (C1) designs. The static
// design (C2) is served by Nginx and does not use this package.
package portal

import (
	"context"
	"errors"
	"fmt"
	"math"
	"math/rand/v2"
	"net/http"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"golang.org/x/sync/singleflight"

	"github.com/k144u/nocrashing/resultbench/internal/dataset"
	"github.com/k144u/nocrashing/resultbench/internal/db"
	"github.com/k144u/nocrashing/resultbench/internal/metrics"
)

// Design names accepted by the portal.
const (
	DesignDB    = "db"    // A: query PostgreSQL on every request
	DesignCache = "cache" // B: Redis cache-aside in front of PostgreSQL
	DesignKV    = "kv"    // C1: pre-computed results in Redis, no database on the read path
)

// Config controls one portal instance.
type Config struct {
	Design    string
	ReleaseAt time.Time // zero means results are already released

	DB    *pgxpool.Pool
	Redis *redis.Client

	CacheTTL   time.Duration
	TTLJitter  float64 // e.g. 0.1 spreads expiry over +-10% of CacheTTL
	Coalesce   bool    // one database query per key in flight (B1)
	XFetch     bool    // probabilistic early recomputation (B2)
	XFetchBeta float64 // 1.0 is the value recommended by Vattani et al.

	// CancelOnDisconnect stops database work when the client goes away. Most
	// real stacks (PHP, servlet containers) keep working, so the default is off,
	// which is what makes impatient refreshes expensive.
	CancelOnDisconnect bool
	WorkTimeout        time.Duration

	// PageCost is spent every time a page is built from the database.
	PageCost PageCost

	// MaxWorkers bounds the requests being processed at once, like a worker
	// pool (PHP-FPM max_children, Apache MaxRequestWorkers). MaxQueue bounds
	// the requests waiting for a worker; beyond that the server answers 503 at
	// once, as a full listen backlog would. Zero means no limit.
	MaxWorkers int
	MaxQueue   int
}

// Server is an http.Handler for one design.
type Server struct {
	cfg Config
	m   *metrics.Registry
	sf  singleflight.Group

	mu       sync.Mutex
	inflight map[int64]int // cache misses currently loading, per key
	seen     sync.Map      // keys that have missed at least once

	reqHist   *metrics.Histogram
	inflightG *metrics.Gauge
	workers   chan struct{}
	queued    atomic.Int64
}

// New builds a server. It panics on an unknown design.
func New(cfg Config) *Server {
	switch cfg.Design {
	case DesignDB, DesignCache, DesignKV:
	default:
		panic("unknown design " + cfg.Design)
	}
	if cfg.WorkTimeout == 0 {
		cfg.WorkTimeout = 30 * time.Second
	}
	if cfg.XFetchBeta == 0 {
		cfg.XFetchBeta = 1
	}
	s := &Server{cfg: cfg, m: metrics.New("portal"), inflight: map[int64]int{}}
	if cfg.MaxWorkers > 0 {
		s.workers = make(chan struct{}, cfg.MaxWorkers)
	}
	s.m.GaugeFunc("queued", s.queued.Load)
	s.reqHist = s.m.Histogram("request")
	s.inflightG = s.m.Gauge("inflight")
	if cfg.DB != nil {
		s.m.GaugeFunc("db_pool_acquired", func() int64 { return int64(cfg.DB.Stat().AcquiredConns()) })
		s.m.GaugeFunc("db_pool_empty_acquires_total", func() int64 { return cfg.DB.Stat().EmptyAcquireCount() })
	}
	return s
}

// Metrics exposes the registry.
func (s *Server) Metrics() *metrics.Registry { return s.m }

// Routes returns the mux with /result, /healthz, /metrics and /stats.
func (s *Server) Routes() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/result", s.handleResult)
	mux.HandleFunc("/healthz", s.handleHealth)
	mux.HandleFunc("/metrics", s.m.ServeMetrics)
	mux.HandleFunc("/stats", s.m.ServeStats)
	return mux
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if s.cfg.DB != nil {
		if err := s.cfg.DB.Ping(ctx); err != nil {
			http.Error(w, "db: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
	}
	if s.cfg.Redis != nil {
		if err := s.cfg.Redis.Ping(ctx).Err(); err != nil {
			http.Error(w, "redis: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
	}
	w.Write([]byte("ok\n"))
}

func writeJSON(w http.ResponseWriter, code int, body []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	w.Write(body)
}

var (
	bodyNotFound = []byte(`{"error":"roll number not found"}`)
	bodyBadRoll  = []byte(`{"error":"invalid roll number"}`)
	bodyInternal = []byte(`{"error":"internal error"}`)
	bodyUnavail  = []byte(`{"error":"service unavailable"}`)
)

// NotReleasedBody is the response before release time.
func NotReleasedBody(releaseAt time.Time) []byte {
	return fmt.Appendf(nil, `{"status":"not_released","release_at_ms":%d}`, releaseAt.UnixMilli())
}

func (s *Server) handleResult(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	s.inflightG.Add(1)
	defer func() {
		s.inflightG.Add(-1)
		s.reqHist.Observe(time.Since(start))
	}()
	s.m.Counter("requests").Inc()

	if s.workers != nil {
		if q := s.queued.Add(1); s.cfg.MaxQueue > 0 && q > int64(s.cfg.MaxQueue) {
			s.queued.Add(-1)
			s.m.Counter("responses_503_queue_full").Inc()
			writeJSON(w, http.StatusServiceUnavailable, bodyUnavail)
			return
		}
		select {
		case s.workers <- struct{}{}:
			s.queued.Add(-1)
			defer func() { <-s.workers }()
		case <-r.Context().Done():
			// The client left while waiting; a request that never started is dropped.
			s.queued.Add(-1)
			s.m.Counter("dropped_before_start").Inc()
			return
		}
	}

	roll, err := strconv.ParseInt(r.URL.Query().Get("roll"), 10, 64)
	if err != nil || roll <= 0 {
		s.m.Counter("responses_400").Inc()
		writeJSON(w, http.StatusBadRequest, bodyBadRoll)
		return
	}
	if !s.cfg.ReleaseAt.IsZero() && start.Before(s.cfg.ReleaseAt) {
		s.m.Counter("responses_425").Inc()
		writeJSON(w, http.StatusTooEarly, NotReleasedBody(s.cfg.ReleaseAt))
		return
	}

	ctx, cancel := s.workContext(r)
	defer cancel()

	var body []byte
	var found bool
	switch s.cfg.Design {
	case DesignDB:
		body, found, err = s.fromDB(ctx, roll)
	case DesignCache:
		body, found, err = s.fromCache(ctx, roll)
	case DesignKV:
		body, found, err = s.fromKV(ctx, roll)
	}
	switch {
	case err != nil:
		s.m.Counter("responses_500").Inc()
		s.m.Counter("errors").Inc()
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
			writeJSON(w, http.StatusServiceUnavailable, bodyUnavail)
			return
		}
		writeJSON(w, http.StatusInternalServerError, bodyInternal)
	case !found:
		s.m.Counter("responses_404").Inc()
		writeJSON(w, http.StatusNotFound, bodyNotFound)
	default:
		s.m.Counter("responses_200").Inc()
		writeJSON(w, http.StatusOK, body)
	}
}

func (s *Server) workContext(r *http.Request) (context.Context, context.CancelFunc) {
	if s.cfg.CancelOnDisconnect {
		return context.WithTimeout(r.Context(), s.cfg.WorkTimeout)
	}
	return context.WithTimeout(context.Background(), s.cfg.WorkTimeout)
}

func (s *Server) fromDB(ctx context.Context, roll int64) ([]byte, bool, error) {
	s.m.Counter("db_queries").Inc()
	rec, ok, err := db.Fetch(ctx, s.cfg.DB, roll)
	if err != nil {
		s.m.Counter("db_errors").Inc()
		return nil, false, err
	}
	if !ok {
		return nil, false, nil
	}
	s.cfg.PageCost.Spend()
	s.m.Counter("pages_built").Inc()
	return dataset.JSON(rec), true, nil
}

// Key is the Redis key used for a roll number by the cache and KV designs.
func Key(roll int64) string { return "r:" + strconv.FormatInt(roll, 10) }

// notFoundMarker is cached for unknown roll numbers so typos do not hit the
// database every time (negative caching).
var notFoundMarker = []byte("-")

func (s *Server) fromKV(ctx context.Context, roll int64) ([]byte, bool, error) {
	v, err := s.cfg.Redis.Get(ctx, Key(roll)).Bytes()
	if err == redis.Nil {
		return nil, false, nil
	}
	if err != nil {
		s.m.Counter("redis_errors").Inc()
		return nil, false, err
	}
	return v, true, nil
}

func (s *Server) fromCache(ctx context.Context, roll int64) ([]byte, bool, error) {
	key := Key(roll)
	v, err := s.cfg.Redis.Get(ctx, key).Bytes()
	switch {
	case err == nil:
		entry, ok := DecodeCacheEntry(v)
		if ok {
			if s.cfg.XFetch && s.shouldRefreshEarly(entry) {
				s.m.Counter("xfetch_early_refresh").Inc()
				return s.load(roll)
			}
			s.m.Counter("cache_hits").Inc()
			if string(entry.Body) == string(notFoundMarker) {
				return nil, false, nil
			}
			return entry.Body, true, nil
		}
		s.m.Counter("cache_bad_entries").Inc()
	case err == redis.Nil:
	default:
		// Cache-aside falls through to the database when the cache is down.
		s.m.Counter("redis_errors").Inc()
	}
	s.countMiss(roll)
	return s.load(roll)
}

// countMiss splits misses into the three kinds that RQ5 needs.
func (s *Server) countMiss(roll int64) {
	s.mu.Lock()
	dup := s.inflight[roll] > 0
	s.mu.Unlock()
	_, seenBefore := s.seen.LoadOrStore(roll, struct{}{})
	switch {
	case dup:
		s.m.Counter("cache_miss_concurrent_duplicate").Inc()
	case seenBefore:
		s.m.Counter("cache_miss_repeat_key").Inc()
	default:
		s.m.Counter("cache_miss_first_time_key").Inc()
	}
}

// load fetches from the database and fills the cache, optionally coalescing
// concurrent loads of the same key.
func (s *Server) load(roll int64) ([]byte, bool, error) {
	s.mu.Lock()
	s.inflight[roll]++
	s.mu.Unlock()
	defer func() {
		s.mu.Lock()
		if s.inflight[roll]--; s.inflight[roll] == 0 {
			delete(s.inflight, roll)
		}
		s.mu.Unlock()
	}()

	fetch := func() (any, error) {
		ctx, cancel := context.WithTimeout(context.Background(), s.cfg.WorkTimeout)
		defer cancel()
		start := time.Now()
		body, found, err := s.fromDB(ctx, roll)
		if err != nil {
			return nil, err
		}
		stored := body
		if !found {
			stored = notFoundMarker
		}
		ttl := s.ttl()
		entry := EncodeCacheEntry(stored, time.Since(start), time.Now().Add(ttl))
		if err := s.cfg.Redis.Set(ctx, Key(roll), entry, ttl).Err(); err != nil {
			s.m.Counter("redis_errors").Inc()
		}
		return result{body, found}, nil
	}
	var v any
	var err error
	if s.cfg.Coalesce {
		var shared bool
		v, err, shared = s.sf.Do(strconv.FormatInt(roll, 10), fetch)
		if shared {
			s.m.Counter("coalesced").Inc()
		}
	} else {
		v, err = fetch()
	}
	if err != nil {
		return nil, false, err
	}
	res := v.(result)
	return res.body, res.found, nil
}

type result struct {
	body  []byte
	found bool
}

func (s *Server) ttl() time.Duration {
	ttl := s.cfg.CacheTTL
	if s.cfg.TTLJitter > 0 {
		f := 1 + s.cfg.TTLJitter*(2*rand.Float64()-1)
		ttl = time.Duration(float64(ttl) * f)
	}
	return ttl
}

// shouldRefreshEarly is the XFetch test from Vattani, Chierichetti and
// Lowenstein (PVLDB 2015): recompute when now - delta*beta*ln(rand) >= expiry.
func (s *Server) shouldRefreshEarly(e CacheEntry) bool {
	r := rand.Float64()
	if r == 0 {
		r = math.SmallestNonzeroFloat64
	}
	gap := time.Duration(float64(e.Delta) * s.cfg.XFetchBeta * -math.Log(r))
	return !time.Now().Add(gap).Before(e.Expiry)
}
