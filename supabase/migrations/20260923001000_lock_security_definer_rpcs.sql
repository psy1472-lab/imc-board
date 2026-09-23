-- Lock SECURITY DEFINER RPCs so the PostgREST anon role cannot call them.
-- Worker/staff RPCs stay available to signed-in users.
-- Helpers used by RLS remain executable by anon/authenticated.
-- Trigger function handle_new_user is granted only to supabase_auth_admin.

DO $$
DECLARE
  proc oid;
  internal_names text[] := ARRAY[
    'imc_provision_auth_user',
    'imc_allocate_worker_id',
    'imc_apply_status',
    'imc_write_audit'
  ];
  authenticated_names text[] := ARRAY[
    'apply_to_notice',
    'cancel_application',
    'check_in_work',
    'check_out_work',
    'claim_staff_role',
    'complete_safety_training',
    'correct_attendance',
    'record_safety_progress',
    'register_worker',
    'transition_application',
    'update_document_status',
    'update_notification_consent'
  ];
  helper_names text[] := ARRAY[
    'imc_current_roles',
    'imc_current_worker_pk',
    'imc_has_role',
    'imc_is_staff'
  ];
BEGIN
  FOR proc IN
    SELECT p.oid
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = ANY (internal_names)
  LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated', proc::regprocedure);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', proc::regprocedure);
  END LOOP;

  FOR proc IN
    SELECT p.oid
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = ANY (authenticated_names)
  LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon', proc::regprocedure);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO authenticated, service_role', proc::regprocedure);
  END LOOP;

  FOR proc IN
    SELECT p.oid
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = ANY (helper_names)
  LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', proc::regprocedure);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO anon, authenticated, service_role', proc::regprocedure);
  END LOOP;
END $$;

REVOKE ALL ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.handle_new_user() TO supabase_auth_admin;

REVOKE ALL ON FUNCTION public.imc_set_updated_at() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.imc_set_updated_at() TO authenticated, service_role, imc_app;

REVOKE ALL ON FUNCTION public.set_bible_entries_updated_at() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.set_bible_entries_updated_at() TO authenticated, service_role;

REVOKE ALL ON FUNCTION public.imc_can_transition(public.imc_application_status, public.imc_application_status)
  FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.imc_can_transition(public.imc_application_status, public.imc_application_status)
  TO authenticated, service_role;

ALTER FUNCTION public.imc_set_updated_at() SET search_path = public;
ALTER FUNCTION public.set_bible_entries_updated_at() SET search_path = public;
ALTER FUNCTION public.imc_can_transition(public.imc_application_status, public.imc_application_status)
  SET search_path = public;
