ALTER TABLE enrollments ADD COLUMN case_id TEXT;
ALTER TABLE enrollments ADD COLUMN athlete_key TEXT;
ALTER TABLE enrollments ADD COLUMN brand TEXT;
ALTER TABLE enrollments ADD COLUMN tier TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_enrollments_case_course
  ON enrollments(case_id, course_id) WHERE case_id IS NOT NULL;
