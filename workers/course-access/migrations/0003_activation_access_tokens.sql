ALTER TABLE enrollments ADD COLUMN access_token_hash TEXT;
ALTER TABLE enrollments ADD COLUMN access_token_expires_at TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_enrollments_access_token
  ON enrollments(access_token_hash) WHERE access_token_hash IS NOT NULL;
