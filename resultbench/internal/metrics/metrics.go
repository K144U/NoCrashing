// Package metrics is a tiny, dependency-free metrics registry that serves
// Prometheus text format on /metrics and a JSON snapshot on /stats.
package metrics

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// Counter is a monotonically increasing value.
type Counter struct{ v atomic.Int64 }

func (c *Counter) Inc()         { c.v.Add(1) }
func (c *Counter) Add(n int64)  { c.v.Add(n) }
func (c *Counter) Value() int64 { return c.v.Load() }

// Gauge is a value that goes up and down.
type Gauge struct{ v atomic.Int64 }

func (g *Gauge) Set(n int64)  { g.v.Store(n) }
func (g *Gauge) Add(n int64)  { g.v.Add(n) }
func (g *Gauge) Value() int64 { return g.v.Load() }

// Histogram counts observations in fixed latency buckets (seconds).
type Histogram struct {
	bounds []float64
	counts []atomic.Int64
	sumUs  atomic.Int64
	n      atomic.Int64
}

// DefaultBuckets covers 1 ms to 60 s.
var DefaultBuckets = []float64{0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60}

func newHistogram(bounds []float64) *Histogram {
	return &Histogram{bounds: bounds, counts: make([]atomic.Int64, len(bounds)+1)}
}

// Observe records one duration.
func (h *Histogram) Observe(d time.Duration) {
	s := d.Seconds()
	i := sort.SearchFloat64s(h.bounds, s)
	h.counts[i].Add(1)
	h.sumUs.Add(d.Microseconds())
	h.n.Add(1)
}

// Registry holds named metrics.
type Registry struct {
	prefix string
	mu     sync.Mutex
	ctrs   map[string]*Counter
	gauges map[string]*Gauge
	hists  map[string]*Histogram
	funcs  map[string]func() int64
}

// New creates a registry whose metric names start with prefix.
func New(prefix string) *Registry {
	return &Registry{prefix: prefix, ctrs: map[string]*Counter{}, gauges: map[string]*Gauge{},
		hists: map[string]*Histogram{}, funcs: map[string]func() int64{}}
}

// Counter returns (creating if needed) the named counter.
func (r *Registry) Counter(name string) *Counter {
	r.mu.Lock()
	defer r.mu.Unlock()
	c, ok := r.ctrs[name]
	if !ok {
		c = &Counter{}
		r.ctrs[name] = c
	}
	return c
}

// Gauge returns (creating if needed) the named gauge.
func (r *Registry) Gauge(name string) *Gauge {
	r.mu.Lock()
	defer r.mu.Unlock()
	g, ok := r.gauges[name]
	if !ok {
		g = &Gauge{}
		r.gauges[name] = g
	}
	return g
}

// GaugeFunc registers a gauge computed on demand.
func (r *Registry) GaugeFunc(name string, f func() int64) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.funcs[name] = f
}

// Histogram returns (creating if needed) the named latency histogram.
func (r *Registry) Histogram(name string) *Histogram {
	r.mu.Lock()
	defer r.mu.Unlock()
	h, ok := r.hists[name]
	if !ok {
		h = newHistogram(DefaultBuckets)
		r.hists[name] = h
	}
	return h
}

// Snapshot returns all counter and gauge values.
func (r *Registry) Snapshot() map[string]int64 {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := map[string]int64{}
	for k, c := range r.ctrs {
		out[k] = c.Value()
	}
	for k, g := range r.gauges {
		out[k] = g.Value()
	}
	for k, f := range r.funcs {
		out[k] = f()
	}
	for k, h := range r.hists {
		out[k+"_count"] = h.n.Load()
		out[k+"_sum_us"] = h.sumUs.Load()
	}
	return out
}

// ServeStats writes the JSON snapshot.
func (r *Registry) ServeStats(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(r.Snapshot())
}

// ServeMetrics writes Prometheus text exposition format.
func (r *Registry) ServeMetrics(w http.ResponseWriter, _ *http.Request) {
	r.mu.Lock()
	defer r.mu.Unlock()
	var b strings.Builder
	for _, k := range sortedKeys(r.ctrs) {
		fmt.Fprintf(&b, "# TYPE %s_%s counter\n%s_%s %d\n", r.prefix, k, r.prefix, k, r.ctrs[k].Value())
	}
	for _, k := range sortedKeys(r.gauges) {
		fmt.Fprintf(&b, "# TYPE %s_%s gauge\n%s_%s %d\n", r.prefix, k, r.prefix, k, r.gauges[k].Value())
	}
	for _, k := range sortedKeys(r.funcs) {
		fmt.Fprintf(&b, "# TYPE %s_%s gauge\n%s_%s %d\n", r.prefix, k, r.prefix, k, r.funcs[k]())
	}
	for _, k := range sortedKeys(r.hists) {
		h := r.hists[k]
		name := r.prefix + "_" + k + "_seconds"
		fmt.Fprintf(&b, "# TYPE %s histogram\n", name)
		var cum int64
		for i, bound := range h.bounds {
			cum += h.counts[i].Load()
			fmt.Fprintf(&b, "%s_bucket{le=\"%g\"} %d\n", name, bound, cum)
		}
		cum += h.counts[len(h.bounds)].Load()
		fmt.Fprintf(&b, "%s_bucket{le=\"+Inf\"} %d\n%s_sum %g\n%s_count %d\n",
			name, cum, name, float64(h.sumUs.Load())/1e6, name, h.n.Load())
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	w.Write([]byte(b.String()))
}

func sortedKeys[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
