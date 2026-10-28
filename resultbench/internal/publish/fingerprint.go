package publish

import (
	"encoding/json"

	"github.com/k144u/nocrashing/resultbench/internal/dataset"
)

func fingerprintOf(body []byte) (uint64, error) {
	var rec dataset.Record
	if err := json.Unmarshal(body, &rec); err != nil {
		return 0, err
	}
	return dataset.Fingerprint(rec), nil
}
