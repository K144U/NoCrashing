-- Schema of a typical, normalised result database.
DROP TABLE IF EXISTS marks, students, schools, subjects, dataset_meta CASCADE;

CREATE TABLE dataset_meta (
    seed                 bigint  NOT NULL,
    n                    integer NOT NULL,
    roll_base            bigint  NOT NULL,
    correction_per_mille integer NOT NULL,
    num_schools          integer NOT NULL,
    complete             boolean NOT NULL
);

CREATE TABLE subjects (
    code text PRIMARY KEY,
    name text NOT NULL,
    ord  integer NOT NULL
);

CREATE TABLE schools (
    school_code integer PRIMARY KEY,
    school_name text NOT NULL,
    district    text NOT NULL
);

CREATE TABLE students (
    roll        bigint PRIMARY KEY,
    name        text NOT NULL,
    father_name text NOT NULL,
    school_code integer NOT NULL REFERENCES schools,
    version     integer NOT NULL
);

-- The primary key on marks is added after the bulk load, which is faster.
CREATE TABLE marks (
    roll         bigint  NOT NULL,
    subject_code text    NOT NULL,
    marks        integer NOT NULL
);
