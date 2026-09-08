import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { verifyAdminPassword } from "../lib/api";
import { clearAdminToken, readAdminToken, writeAdminToken } from "../lib/adminToken";

const ADMIN_SESSION_KEY = "imc_admin_authenticated";

type AdminAuthContextValue = {
  isAdmin: boolean;
  loading: boolean;
  error: string | null;
  login: (password: string) => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
};

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null);

function readAdminSession() {
  return sessionStorage.getItem(ADMIN_SESSION_KEY) === "true" && Boolean(readAdminToken());
}

export function AdminAuthProvider({ children }: { children: React.ReactNode }) {
  const [isAdmin, setIsAdmin] = useState(readAdminSession);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (password: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await verifyAdminPassword(password);
      writeAdminToken(result.token);
      sessionStorage.setItem(ADMIN_SESSION_KEY, "true");
      setIsAdmin(true);
      return true;
    } catch {
      setError("관리자 비밀번호가 올바르지 않습니다.");
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(ADMIN_SESSION_KEY);
    clearAdminToken();
    setIsAdmin(false);
    setError(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({
      isAdmin,
      loading,
      error,
      login,
      logout,
      clearError,
    }),
    [isAdmin, loading, error, login, logout, clearError],
  );

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

export function useAdminAuth() {
  const context = useContext(AdminAuthContext);
  if (!context) {
    throw new Error("useAdminAuth must be used within AdminAuthProvider");
  }
  return context;
}
