CREATE TABLE click_totals (
  essay TEXT NOT NULL,
  day INTEGER NOT NULL,
  is_test INTEGER NOT NULL,
  clicks INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (essay,day,is_test)
);
