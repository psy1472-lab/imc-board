CREATE TABLE IF NOT EXISTS hourly_unloading (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    hour_slot TEXT NOT NULL,
    collection_vehicles INTEGER,
    quota_vehicles INTEGER,
    arrival_vehicles INTEGER,
    exchange_vehicles INTEGER,
    PRIMARY KEY (report_date, hour_slot)
);

CREATE INDEX IF NOT EXISTS hourly_unloading_report_date_idx
    ON hourly_unloading (report_date);
