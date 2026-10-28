CREATE TABLE attempts (
  email_hash TEXT PRIMARY KEY,
  article TEXT NOT NULL,
  attempted_at INTEGER NOT NULL,
  accepted INTEGER NOT NULL DEFAULT 0,
  is_test INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE subscribers (
  email_hash TEXT PRIMARY KEY,
  confirmed_at INTEGER NOT NULL,
  article TEXT,
  source TEXT NOT NULL,
  is_test INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE receipts (
  message_id TEXT PRIMARY KEY,
  received_at INTEGER NOT NULL
);
CREATE TABLE clicks (
  essay TEXT NOT NULL,
  visitor_hash TEXT NOT NULL,
  clicked_at INTEGER NOT NULL,
  is_test INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (essay, visitor_hash)
);
CREATE TABLE health (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE INDEX subscriber_date ON subscribers(confirmed_at);
CREATE INDEX click_date ON clicks(clicked_at);
