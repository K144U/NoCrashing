// Package db holds the PostgreSQL schema, the bulk loader, the per-request
// query used by the database-backed design, and the correction job.
package db

import (
	"context"
	_ "embed"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/k144u/nocrashing/resultbench/internal/dataset"
)

//go:embed schema.sql
var schemaSQL string

// Connect opens a pool. maxConns <= 0 keeps the pgx default.
func Connect(ctx context.Context, dsn string, maxConns int) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, err
	}
	if maxConns > 0 {
		cfg.MaxConns = int32(maxConns)
	}
	return pgxpool.NewWithConfig(ctx, cfg)
}

// WaitReady retries until the database accepts queries or the timeout passes.
func WaitReady(ctx context.Context, pool *pgxpool.Pool, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		err := pool.Ping(ctx)
		if err == nil {
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("database not ready after %s: %w", timeout, err)
		}
		time.Sleep(500 * time.Millisecond)
	}
}

// LoadedConfig returns the dataset recorded in the database, if any.
func LoadedConfig(ctx context.Context, pool *pgxpool.Pool) (cfg dataset.Config, ok bool, err error) {
	var exists bool
	if err = pool.QueryRow(ctx, `SELECT to_regclass('public.dataset_meta') IS NOT NULL`).Scan(&exists); err != nil || !exists {
		return cfg, false, err
	}
	err = pool.QueryRow(ctx, `SELECT seed, n, roll_base, correction_per_mille, num_schools FROM dataset_meta WHERE complete`).
		Scan(&cfg.Seed, &cfg.N, &cfg.RollBase, &cfg.CorrectionPerMille, &cfg.NumSchools)
	if err == pgx.ErrNoRows {
		return cfg, false, nil
	}
	return cfg, err == nil, err
}

// Load drops and recreates the schema and bulk-loads the dataset. It is
// skipped when the same dataset is already loaded, unless force is set.
func Load(ctx context.Context, pool *pgxpool.Pool, cfg dataset.Config, force bool, progress func(done int)) (skipped bool, err error) {
	if !force {
		have, ok, err := LoadedConfig(ctx, pool)
		if err != nil {
			return false, err
		}
		if ok && have == cfg {
			return true, nil
		}
	}
	if _, err := pool.Exec(ctx, schemaSQL); err != nil {
		return false, fmt.Errorf("schema: %w", err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO dataset_meta VALUES ($1,$2,$3,$4,$5,false)`,
		cfg.Seed, cfg.N, cfg.RollBase, cfg.CorrectionPerMille, cfg.NumSchools); err != nil {
		return false, err
	}

	subjects := make([][]any, len(dataset.Subjects))
	for k, s := range dataset.Subjects {
		subjects[k] = []any{s.Code, s.Name, k}
	}
	if _, err := pool.CopyFrom(ctx, pgx.Identifier{"subjects"}, []string{"code", "name", "ord"}, pgx.CopyFromRows(subjects)); err != nil {
		return false, fmt.Errorf("subjects: %w", err)
	}
	schools := make([][]any, 0, cfg.NumSchools)
	for code := 1000; code < 1000+cfg.NumSchools; code++ {
		s := cfg.SchoolByCode(code)
		schools = append(schools, []any{s.Code, s.Name, s.District})
	}
	if _, err := pool.CopyFrom(ctx, pgx.Identifier{"schools"}, []string{"school_code", "school_name", "district"}, pgx.CopyFromRows(schools)); err != nil {
		return false, fmt.Errorf("schools: %w", err)
	}

	const batch = 50_000
	for start := 0; start < cfg.N; start += batch {
		end := min(start+batch, cfg.N)
		students := make([][]any, 0, end-start)
		marks := make([][]any, 0, (end-start)*len(dataset.Subjects))
		for i := start; i < end; i++ {
			r := cfg.Original(i)
			students = append(students, []any{r.Roll, r.Name, r.FatherName, r.SchoolCode, r.Version})
			for _, m := range r.Marks {
				marks = append(marks, []any{r.Roll, m.Code, m.Marks})
			}
		}
		if _, err := pool.CopyFrom(ctx, pgx.Identifier{"students"}, []string{"roll", "name", "father_name", "school_code", "version"}, pgx.CopyFromRows(students)); err != nil {
			return false, fmt.Errorf("students: %w", err)
		}
		if _, err := pool.CopyFrom(ctx, pgx.Identifier{"marks"}, []string{"roll", "subject_code", "marks"}, pgx.CopyFromRows(marks)); err != nil {
			return false, fmt.Errorf("marks: %w", err)
		}
		if progress != nil {
			progress(end)
		}
	}
	if _, err := pool.Exec(ctx, `ALTER TABLE marks ADD PRIMARY KEY (roll, subject_code); ANALYZE;`); err != nil {
		return false, err
	}
	_, err = pool.Exec(ctx, `UPDATE dataset_meta SET complete = true`)
	return false, err
}

// resultQuery is what a typical database-backed portal runs on every
// request: join the student, school and marks tables for one roll number.
const resultQuery = `
SELECT s.name, s.father_name, s.version, sc.school_code, sc.school_name, sc.district,
       m.subject_code, sub.name, m.marks
FROM students s
JOIN schools sc ON sc.school_code = s.school_code
JOIN marks m ON m.roll = s.roll
JOIN subjects sub ON sub.code = m.subject_code
WHERE s.roll = $1
ORDER BY sub.ord`

// Querier is satisfied by *pgxpool.Pool and pgx.Tx.
type Querier interface {
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// Fetch returns the current result for one roll number. ok is false when the
// roll number does not exist.
func Fetch(ctx context.Context, q Querier, roll int64) (rec dataset.Record, ok bool, err error) {
	rows, err := q.Query(ctx, resultQuery, roll)
	if err != nil {
		return rec, false, err
	}
	defer rows.Close()
	for rows.Next() {
		var m dataset.Mark
		if err := rows.Scan(&rec.Name, &rec.FatherName, &rec.Version, &rec.SchoolCode, &rec.SchoolName, &rec.District,
			&m.Code, &m.Name, &m.Marks); err != nil {
			return rec, false, err
		}
		rec.Marks = append(rec.Marks, m)
	}
	if err := rows.Err(); err != nil {
		return rec, false, err
	}
	if len(rec.Marks) == 0 {
		return rec, false, nil
	}
	rec.Roll = roll
	dataset.Finalize(&rec)
	return rec, true, nil
}

// Stream reads every result in roll order and calls fn for each. It is the
// read side of the materialization pipeline.
func Stream(ctx context.Context, pool *pgxpool.Pool, fn func(dataset.Record) error) error {
	rows, err := pool.Query(ctx, `
SELECT s.roll, s.name, s.father_name, s.version, sc.school_code, sc.school_name, sc.district,
       array_agg(m.subject_code ORDER BY sub.ord), array_agg(sub.name ORDER BY sub.ord), array_agg(m.marks ORDER BY sub.ord)
FROM students s
JOIN schools sc ON sc.school_code = s.school_code
JOIN marks m ON m.roll = s.roll
JOIN subjects sub ON sub.code = m.subject_code
GROUP BY s.roll, sc.school_code
ORDER BY s.roll`)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var rec dataset.Record
		var codes, names []string
		var marks []int32
		if err := rows.Scan(&rec.Roll, &rec.Name, &rec.FatherName, &rec.Version, &rec.SchoolCode, &rec.SchoolName, &rec.District,
			&codes, &names, &marks); err != nil {
			return err
		}
		rec.Marks = make([]dataset.Mark, len(codes))
		for k := range codes {
			rec.Marks[k] = dataset.Mark{Code: codes[k], Name: names[k], Marks: int(marks[k])}
		}
		dataset.Finalize(&rec)
		if err := fn(rec); err != nil {
			return err
		}
	}
	return rows.Err()
}

// ApplyCorrections writes the revised marks for every corrected student (or
// reverts them to the original when revert is set) in one transaction, and
// returns the roll numbers it changed.
func ApplyCorrections(ctx context.Context, pool *pgxpool.Pool, cfg dataset.Config, revert bool) ([]int64, error) {
	var rows [][]any
	var rolls []int64
	for i := 0; i < cfg.N; i++ {
		if !cfg.IsCorrected(i) {
			continue
		}
		rec := cfg.Current(i, !revert)
		rolls = append(rolls, rec.Roll)
		for _, m := range rec.Marks {
			rows = append(rows, []any{rec.Roll, m.Code, m.Marks, rec.Version})
		}
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, `CREATE TEMP TABLE corr (roll bigint, subject_code text, marks int, version int) ON COMMIT DROP`); err != nil {
		return nil, err
	}
	if _, err := tx.CopyFrom(ctx, pgx.Identifier{"corr"}, []string{"roll", "subject_code", "marks", "version"}, pgx.CopyFromRows(rows)); err != nil {
		return nil, err
	}
	if _, err := tx.Exec(ctx, `
UPDATE marks m SET marks = c.marks FROM corr c WHERE m.roll = c.roll AND m.subject_code = c.subject_code;
UPDATE students s SET version = c.version FROM (SELECT DISTINCT roll, version FROM corr) c WHERE s.roll = c.roll;`); err != nil {
		return nil, err
	}
	return rolls, tx.Commit(ctx)
}
