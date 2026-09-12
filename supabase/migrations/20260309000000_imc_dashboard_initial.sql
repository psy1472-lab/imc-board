-- PostgreSQL schema for Supabase (converted from SQLite migrations 001 + 002)
-- Apply via: supabase db reset / supabase migration up

CREATE TABLE IF NOT EXISTS report_metadata (
    report_date DATE PRIMARY KEY,
    center_name TEXT,
    report_format TEXT,
    day_type TEXT,
    file_path TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_summary (
    report_date DATE PRIMARY KEY REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    center_name TEXT,
    national_volume INTEGER,
    total_volume INTEGER,
    dispatch_volume INTEGER,
    arrival_volume INTEGER,
    remaining_volume INTEGER,
    productivity DOUBLE PRECISION,
    ips_rate DOUBLE PRECISION,
    last_operation_time TEXT,
    communication_status TEXT,
    raw_values JSONB
);

CREATE TABLE IF NOT EXISTS hourly_throughput (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    hour_slot TEXT NOT NULL,
    dispatch_volume INTEGER,
    arrival_volume INTEGER,
    total_volume INTEGER,
    PRIMARY KEY (report_date, hour_slot)
);

CREATE TABLE IF NOT EXISTS staffing (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    hour_slot TEXT NOT NULL,
    actual_staff INTEGER,
    productivity DOUBLE PRECISION,
    absence_rate DOUBLE PRECISION,
    PRIMARY KEY (report_date, hour_slot)
);

CREATE TABLE IF NOT EXISTS quota_exchange (
    report_date DATE PRIMARY KEY REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    quarter_standard INTEGER,
    quarter_actual INTEGER,
    quarter_difference INTEGER,
    exchange_standard INTEGER,
    exchange_actual INTEGER,
    exchange_difference INTEGER,
    exchange_remaining INTEGER
);

CREATE TABLE IF NOT EXISTS transport_office (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    office_name TEXT NOT NULL,
    volume INTEGER,
    vehicles_actual INTEGER,
    vehicles_standard INTEGER,
    last_arrival_time TEXT,
    delay_minutes INTEGER,
    status TEXT,
    PRIMARY KEY (report_date, office_name)
);

CREATE TABLE IF NOT EXISTS sorting_machine (
    report_date DATE PRIMARY KEY REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    total_supply INTEGER,
    total_sorted INTEGER,
    sorting_rate DOUBLE PRECISION,
    ips_rate DOUBLE PRECISION,
    reject_rate DOUBLE PRECISION,
    shortcut_rate DOUBLE PRECISION,
    avg_throughput INTEGER,
    peak_throughput INTEGER,
    unread_count INTEGER,
    unread_rate DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS safety_summary (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    category TEXT NOT NULL,
    label TEXT,
    passed_items INTEGER,
    total_items INTEGER,
    status TEXT,
    PRIMARY KEY (report_date, category)
);

CREATE TABLE IF NOT EXISTS safety_incident (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    department TEXT,
    victim_name TEXT,
    gender TEXT,
    occurrence_time TEXT,
    injury_type TEXT,
    description TEXT,
    PRIMARY KEY (report_date, seq)
);

CREATE TABLE IF NOT EXISTS anomaly (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    category TEXT,
    severity TEXT,
    message TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS validation_log (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    rule_name TEXT,
    status TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS kpi_comparison (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    current_value DOUBLE PRECISION,
    compare_value DOUBLE PRECISION,
    difference DOUBLE PRECISION,
    difference_percent DOUBLE PRECISION,
    trend TEXT,
    compare_basis TEXT,
    PRIMARY KEY (report_date, metric_name, compare_basis)
);

CREATE TABLE IF NOT EXISTS threshold_config (
    metric_name TEXT PRIMARY KEY,
    caution_min DOUBLE PRECISION,
    caution_max DOUBLE PRECISION,
    warning_min DOUBLE PRECISION,
    warning_max DOUBLE PRECISION,
    critical_min DOUBLE PRECISION,
    critical_max DOUBLE PRECISION
);

INSERT INTO threshold_config (metric_name, warning_min, critical_min)
VALUES ('ips_rate', 97.0, 95.0)
ON CONFLICT (metric_name) DO NOTHING;

CREATE TABLE IF NOT EXISTS operation_period (
    id BIGSERIAL PRIMARY KEY,
    period_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operation_period_dates
    ON operation_period (start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_operation_period_type
    ON operation_period (period_type);

CREATE INDEX IF NOT EXISTS idx_report_metadata_ingested
    ON report_metadata (ingested_at DESC);
