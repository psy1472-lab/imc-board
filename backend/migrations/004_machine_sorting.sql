CREATE TABLE IF NOT EXISTS machine_sorting (
    report_date TEXT NOT NULL,
    stream TEXT NOT NULL,
    deck INTEGER NOT NULL,
    volume INTEGER,
    share_rate REAL,
    PRIMARY KEY (report_date, stream, deck)
);
