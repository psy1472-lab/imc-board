-- Lock IMC operations tables behind RLS.
-- They were in public with GRANT ALL to anon/authenticated and RLS off,
-- so anyone with the project URL + anon key could read, edit, or delete all rows.
-- Backend access stays on the imc_app role (Railway DATABASE_URL).
-- service_role keeps BYPASSRLS. Client roles get no policies and lose table grants.

DO $$
DECLARE
  tbl text;
  tables text[] := ARRAY[
    'report_metadata',
    'daily_summary',
    'hourly_throughput',
    'staffing',
    'quota_exchange',
    'transport_office',
    'sorting_machine',
    'safety_summary',
    'safety_incident',
    'anomaly',
    'validation_log',
    'threshold_config',
    'kpi_comparison',
    'operation_period',
    'daily_forecast',
    'machine_sorting'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('DROP POLICY IF EXISTS imc_app_all ON public.%I', tbl);
    EXECUTE format(
      'CREATE POLICY imc_app_all ON public.%I FOR ALL TO imc_app USING (true) WITH CHECK (true)',
      tbl
    );
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', tbl);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon', tbl);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM authenticated', tbl);
    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.%I TO imc_app',
      tbl
    );
    EXECUTE format('GRANT ALL ON TABLE public.%I TO service_role', tbl);
  END LOOP;
END $$;

DO $$
DECLARE
  seq record;
BEGIN
  FOR seq IN
    SELECT DISTINCT n.nspname AS schema_name, c.relname AS sequence_name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_depend d ON d.objid = c.oid
    JOIN pg_class t ON t.oid = d.refobjid
    JOIN pg_namespace tn ON tn.oid = t.relnamespace
    WHERE c.relkind = 'S'
      AND n.nspname = 'public'
      AND tn.nspname = 'public'
      AND t.relname IN ('anomaly', 'validation_log', 'operation_period')
  LOOP
    EXECUTE format(
      'REVOKE ALL ON SEQUENCE %I.%I FROM PUBLIC, anon, authenticated',
      seq.schema_name,
      seq.sequence_name
    );
    EXECUTE format(
      'GRANT USAGE, SELECT ON SEQUENCE %I.%I TO imc_app, service_role',
      seq.schema_name,
      seq.sequence_name
    );
  END LOOP;
END $$;
