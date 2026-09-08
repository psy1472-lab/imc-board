CREATE TABLE IF NOT EXISTS operation_period (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_operation_period_dates
    ON operation_period (start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_operation_period_type
    ON operation_period (period_type);
