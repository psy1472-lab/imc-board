-- Move RLS helper functions out of the PostgREST-exposed public schema.
-- public wrappers stay SECURITY INVOKER so anon cannot hit SECURITY DEFINER RPCs.
-- The private copies keep SECURITY DEFINER so they can read user_roles under RLS.

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;
GRANT USAGE ON SCHEMA private TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION private.imc_is_staff()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid()
      AND role IN ('OPERATOR', 'HR_CONTRACT', 'PAYROLL', 'ADMIN')
  );
$$;

CREATE OR REPLACE FUNCTION private.imc_has_role(p_role public.imc_app_role)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = p_role
  );
$$;

CREATE OR REPLACE FUNCTION private.imc_current_roles()
RETURNS public.imc_app_role[]
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(array_agg(role), '{}')
  FROM public.user_roles
  WHERE user_id = auth.uid();
$$;

CREATE OR REPLACE FUNCTION private.imc_current_worker_pk()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT id FROM public.workers WHERE auth_user_id = auth.uid() LIMIT 1;
$$;

REVOKE ALL ON FUNCTION private.imc_is_staff() FROM PUBLIC;
REVOKE ALL ON FUNCTION private.imc_has_role(public.imc_app_role) FROM PUBLIC;
REVOKE ALL ON FUNCTION private.imc_current_roles() FROM PUBLIC;
REVOKE ALL ON FUNCTION private.imc_current_worker_pk() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION private.imc_is_staff() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION private.imc_has_role(public.imc_app_role) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION private.imc_current_roles() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION private.imc_current_worker_pk() TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.imc_is_staff()
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = private
AS $$
  SELECT private.imc_is_staff();
$$;

CREATE OR REPLACE FUNCTION public.imc_has_role(p_role public.imc_app_role)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = private
AS $$
  SELECT private.imc_has_role(p_role);
$$;

CREATE OR REPLACE FUNCTION public.imc_current_roles()
RETURNS public.imc_app_role[]
LANGUAGE sql
STABLE
SET search_path = private
AS $$
  SELECT private.imc_current_roles();
$$;

CREATE OR REPLACE FUNCTION public.imc_current_worker_pk()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = private
AS $$
  SELECT private.imc_current_worker_pk();
$$;

REVOKE ALL ON FUNCTION public.imc_is_staff() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.imc_has_role(public.imc_app_role) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.imc_current_roles() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.imc_current_worker_pk() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.imc_is_staff() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.imc_has_role(public.imc_app_role) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.imc_current_roles() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.imc_current_worker_pk() TO anon, authenticated, service_role;

-- Existing SECURITY DEFINER RPCs still call public.imc_* helpers.
-- Those now resolve to INVOKER wrappers, which call private copies as the current user.
-- Private copies are SECURITY DEFINER, so user_roles remains readable.
