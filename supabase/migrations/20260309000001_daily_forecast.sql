CREATE TABLE IF NOT EXISTS daily_forecast (
    report_date DATE PRIMARY KEY,
    target_date DATE NOT NULL,
    forecast_volume NUMERIC,
    forecast_national_volume NUMERIC,
    method TEXT,
    method_label TEXT,
    forecast_text TEXT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
