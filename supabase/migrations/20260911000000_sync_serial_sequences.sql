-- Bulk copies of SQLite rows set explicit ids and leave BIGSERIAL sequences behind.
-- Uploads then collide on anomaly_pkey / validation_log_pkey.
SELECT setval(
    pg_get_serial_sequence('anomaly', 'id'),
    COALESCE((SELECT MAX(id) FROM anomaly), 1),
    COALESCE((SELECT MAX(id) FROM anomaly), 0) > 0
);
SELECT setval(
    pg_get_serial_sequence('validation_log', 'id'),
    COALESCE((SELECT MAX(id) FROM validation_log), 1),
    COALESCE((SELECT MAX(id) FROM validation_log), 0) > 0
);
SELECT setval(
    pg_get_serial_sequence('operation_period', 'id'),
    COALESCE((SELECT MAX(id) FROM operation_period), 1),
    COALESCE((SELECT MAX(id) FROM operation_period), 0) > 0
);
