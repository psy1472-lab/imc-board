CREATE TABLE IF NOT EXISTS report_metadata (
    report_date TEXT PRIMARY KEY,
    center_name TEXT,
    report_format TEXT,
    day_type TEXT,
    file_path TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_summary (
    report_date TEXT PRIMARY KEY,
    center_name TEXT,
    national_volume INTEGER,
    total_volume INTEGER,
    dispatch_volume INTEGER,
    arrival_volume INTEGER,
    remaining_volume INTEGER,
    productivity REAL,
    ips_rate REAL,
    last_operation_time TEXT,
    communication_status TEXT,
    raw_values TEXT
);

CREATE TABLE IF NOT EXISTS hourly_throughput (
    report_date TEXT NOT NULL,
    hour_slot TEXT NOT NULL,
    dispatch_volume INTEGER,
    arrival_volume INTEGER,
    total_volume INTEGER,
    PRIMARY KEY (report_date, hour_slot)
);

CREATE TABLE IF NOT EXISTS staffing (
    report_date TEXT NOT NULL,
    hour_slot TEXT NOT NULL,
    actual_staff INTEGER,
    productivity REAL,
    absence_rate REAL,
    PRIMARY KEY (report_date, hour_slot)
);

CREATE TABLE IF NOT EXISTS quota_exchange (
    report_date TEXT PRIMARY KEY,
    quarter_standard INTEGER,
    quarter_actual INTEGER,
    quarter_difference INTEGER,
    exchange_standard INTEGER,
    exchange_actual INTEGER,
    exchange_difference INTEGER,
    exchange_remaining INTEGER
);

CREATE TABLE IF NOT EXISTS transport_office (
    report_date TEXT NOT NULL,
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
    report_date TEXT PRIMARY KEY,
    total_supply INTEGER,
    total_sorted INTEGER,
    sorting_rate REAL,
    ips_rate REAL,
    reject_rate REAL,
    shortcut_rate REAL,
    avg_throughput INTEGER,
    peak_throughput INTEGER,
    unread_count INTEGER,
    unread_rate REAL
);

CREATE TABLE IF NOT EXISTS safety_summary (
    report_date TEXT NOT NULL,
    category TEXT NOT NULL,
    label TEXT,
    passed_items INTEGER,
    total_items INTEGER,
    status TEXT,
    PRIMARY KEY (report_date, category)
);

CREATE TABLE IF NOT EXISTS safety_incident (
    report_date TEXT NOT NULL,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    category TEXT,
    severity TEXT,
    message TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS validation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    rule_name TEXT,
    status TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS kpi_comparison (
    report_date TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    current_value REAL,
    compare_value REAL,
    difference REAL,
    difference_percent REAL,
    trend TEXT,
    compare_basis TEXT,
    PRIMARY KEY (report_date, metric_name, compare_basis)
);

CREATE TABLE IF NOT EXISTS threshold_config (
    metric_name TEXT PRIMARY KEY,
    caution_min REAL,
    caution_max REAL,
    warning_min REAL,
    warning_max REAL,
    critical_min REAL,
    critical_max REAL
);

INSERT OR IGNORE INTO threshold_config (metric_name, warning_min, critical_min)
VALUES ('ips_rate', 97.0, 95.0);
