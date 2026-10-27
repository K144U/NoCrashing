package portal

import (
	"testing"
	"time"
)

func TestCacheEntryRoundTrip(t *testing.T) {
	exp := time.UnixMilli(1_700_000_000_123)
	v := EncodeCacheEntry([]byte(`{"roll":1,"name":"a|b"}`), 1234*time.Microsecond, exp)
	e, ok := DecodeCacheEntry(v)
	if !ok || e.Delta != 1234*time.Microsecond || !e.Expiry.Equal(exp) || string(e.Body) != `{"roll":1,"name":"a|b"}` {
		t.Fatalf("round trip failed: %+v %v", e, ok)
	}
	if _, ok := DecodeCacheEntry([]byte(`{"roll":1}`)); ok {
		t.Fatal("raw JSON decoded as an entry")
	}
}

func TestXFetchProbabilityRisesNearExpiry(t *testing.T) {
	s := New(Config{Design: DesignCache, XFetch: true, XFetchBeta: 1})
	count := func(remaining time.Duration) int {
		e := CacheEntry{Delta: 10 * time.Millisecond, Expiry: time.Now().Add(remaining)}
		n := 0
		for i := 0; i < 2000; i++ {
			if s.shouldRefreshEarly(e) {
				n++
			}
		}
		return n
	}
	far, near := count(time.Second), count(5*time.Millisecond)
	if far > 5 || near < 500 {
		t.Fatalf("early refresh counts far=%d near=%d", far, near)
	}
}
