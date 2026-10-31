CREATE TABLE rate_buckets (
  bucket TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  requests INTEGER NOT NULL DEFAULT 1
);
