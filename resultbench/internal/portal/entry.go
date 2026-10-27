package portal

import (
	"bytes"
	"strconv"
	"time"
)

// CacheEntry is a value stored by the cache-aside design. Besides the body it
// records how long the value took to compute (delta) and when it expires,
// which XFetch needs.
type CacheEntry struct {
	Delta  time.Duration
	Expiry time.Time
	Body   []byte
}

// EncodeCacheEntry renders "<delta_us>|<expiry_unix_ms>|<body>".
func EncodeCacheEntry(body []byte, delta time.Duration, expiry time.Time) []byte {
	b := make([]byte, 0, len(body)+32)
	b = strconv.AppendInt(b, delta.Microseconds(), 10)
	b = append(b, '|')
	b = strconv.AppendInt(b, expiry.UnixMilli(), 10)
	b = append(b, '|')
	return append(b, body...)
}

// DecodeCacheEntry parses an encoded entry.
func DecodeCacheEntry(v []byte) (CacheEntry, bool) {
	i := bytes.IndexByte(v, '|')
	if i < 0 {
		return CacheEntry{}, false
	}
	j := bytes.IndexByte(v[i+1:], '|')
	if j < 0 {
		return CacheEntry{}, false
	}
	j += i + 1
	d, err1 := strconv.ParseInt(string(v[:i]), 10, 64)
	e, err2 := strconv.ParseInt(string(v[i+1:j]), 10, 64)
	if err1 != nil || err2 != nil {
		return CacheEntry{}, false
	}
	return CacheEntry{Delta: time.Duration(d) * time.Microsecond, Expiry: time.UnixMilli(e), Body: v[j+1:]}, true
}
