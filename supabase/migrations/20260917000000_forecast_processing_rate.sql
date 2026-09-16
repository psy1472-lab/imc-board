ALTER TABLE daily_forecast
    ADD COLUMN IF NOT EXISTS forecast_processing_rate NUMERIC;
