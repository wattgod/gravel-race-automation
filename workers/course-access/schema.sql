-- Gravel God Course Platform — D1 Schema
-- Run: wrangler d1 execute course-platform --file=schema.sql

-- Users (created on first verify or webhook)
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  email_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  total_xp INTEGER DEFAULT 0,
  current_streak INTEGER DEFAULT 0,
  longest_streak INTEGER DEFAULT 0,
  last_active_date TEXT,
  nudge_unsubscribed INTEGER DEFAULT 0
);

-- Course enrollments (created by Stripe webhook)
CREATE TABLE IF NOT EXISTS enrollments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  course_id TEXT NOT NULL,
  purchased_at TEXT DEFAULT (datetime('now')),
  stripe_session_id TEXT,
  amount_cents INTEGER,
  currency TEXT DEFAULT 'usd',
  UNIQUE(user_id, course_id)
);

-- Lesson progress (one row per lesson completion)
CREATE TABLE IF NOT EXISTS lesson_progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  course_id TEXT NOT NULL,
  lesson_id TEXT NOT NULL,
  completed_at TEXT DEFAULT (datetime('now')),
  UNIQUE(user_id, course_id, lesson_id)
);

-- Knowledge check answers (for analytics + XP)
CREATE TABLE IF NOT EXISTS knowledge_check_answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  course_id TEXT NOT NULL,
  lesson_id TEXT NOT NULL,
  question_hash TEXT NOT NULL,
  selected_index INTEGER NOT NULL,
  correct INTEGER NOT NULL,
  answered_at TEXT DEFAULT (datetime('now')),
  UNIQUE(user_id, course_id, lesson_id, question_hash)
);

-- XP log (every XP award is a row — auditable)
CREATE TABLE IF NOT EXISTS xp_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  course_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  xp_amount INTEGER NOT NULL,
  reference_id TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

-- Streak history (one row per active day)
CREATE TABLE IF NOT EXISTS streak_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  active_date TEXT NOT NULL,
  UNIQUE(user_id, active_date)
);

-- Nudge email log (prevents duplicate sends)
CREATE TABLE IF NOT EXISTS nudge_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  nudge_type TEXT NOT NULL,
  course_id TEXT,
  sent_at TEXT DEFAULT (datetime('now')),
  UNIQUE(user_id, nudge_type, course_id, sent_at)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_enrollments_user ON enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_lesson_progress_user_course ON lesson_progress(user_id, course_id);
CREATE INDEX IF NOT EXISTS idx_xp_log_user ON xp_log(user_id);
CREATE INDEX IF NOT EXISTS idx_streak_user ON streak_history(user_id, active_date);
CREATE INDEX IF NOT EXISTS idx_nudge_user ON nudge_log(user_id, nudge_type);
