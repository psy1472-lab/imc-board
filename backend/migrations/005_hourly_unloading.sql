CREATE TABLE IF NOT EXISTS hourly_unloading (
    report_date TEXT NOT NULL,
    hour_slot TEXT NOT NULL,
    collection_vehicles INTEGER,
    quota_vehicles INTEGER,
    arrival_vehicles INTEGER,
    exchange_vehicles INTEGER,
    PRIMARY KEY (report_date, hour_slot)
);
