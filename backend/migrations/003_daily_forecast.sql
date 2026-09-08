CREATE TABLE IF NOT EXISTS daily_forecast (
    report_date TEXT PRIMARY KEY,
    target_date TEXT NOT NULL,
    forecast_volume REAL,
    forecast_national_volume REAL,
    method TEXT,
    method_label TEXT,
    forecast_text TEXT,
    generated_at TEXT NOT NULL
);
