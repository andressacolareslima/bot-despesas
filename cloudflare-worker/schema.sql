CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sender TEXT NOT NULL,
  amount REAL NOT NULL,
  expense_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_messages (
  message_id TEXT PRIMARY KEY
);

CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);