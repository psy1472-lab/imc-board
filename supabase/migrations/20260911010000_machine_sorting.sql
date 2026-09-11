CREATE TABLE IF NOT EXISTS machine_sorting (
    report_date DATE NOT NULL REFERENCES report_metadata(report_date) ON DELETE CASCADE,
    stream TEXT NOT NULL,
    deck INTEGER NOT NULL,
    volume INTEGER,
    share_rate DOUBLE PRECISION,
    PRIMARY KEY (report_date, stream, deck)
);

CREATE INDEX IF NOT EXISTS machine_sorting_report_date_idx
    ON machine_sorting (report_date);
