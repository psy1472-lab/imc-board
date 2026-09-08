const ADMIN_TOKEN_KEY = "imc_admin_token";

export function readAdminToken(): string | null {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

export function writeAdminToken(token: string) {
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken() {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function adminAuthHeaders(): HeadersInit {
  const token = readAdminToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
