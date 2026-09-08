import { useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { useAdminAuth } from "../../context/AdminAuthContext";

type Props = {
  title: string;
  description?: string;
};

export function AdminLoginPanel({ title, description }: Props) {
  const { palette } = useTheme();
  const { login, loading, error, clearError } = useAdminAuth();
  const [password, setPassword] = useState("");

  const panelStyle = {
    background: palette.panel,
    border: `1px solid ${palette.border}`,
    borderRadius: 14,
    padding: 24,
    width: "min(420px, 100%)",
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!password.trim()) return;
    await login(password);
  };

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: 360,
        padding: 24,
      }}
    >
      <form onSubmit={(event) => void handleSubmit(event)} style={panelStyle}>
        <div style={{ fontSize: 12, color: palette.caution, fontWeight: 600, marginBottom: 8 }}>관리자 모드</div>
        <h2 style={{ margin: "0 0 8px", fontSize: 22 }}>{title}</h2>
        <p style={{ margin: "0 0 20px", color: palette.muted, fontSize: 14, lineHeight: 1.6 }}>
          {description ?? "이 화면은 관리자만 접근할 수 있습니다. 비밀번호를 입력해 주세요."}
        </p>
        <label style={{ display: "grid", gap: 8, marginBottom: 16 }}>
          <span style={{ fontSize: 13, color: palette.muted }}>관리자 비밀번호</span>
          <input
            type="password"
            value={password}
            onChange={(event) => {
              clearError();
              setPassword(event.target.value);
            }}
            autoComplete="current-password"
            placeholder="비밀번호 입력"
            style={{
              padding: "10px 12px",
              background: palette.inputBg,
              color: palette.text,
              border: `1px solid ${error ? palette.critical : palette.border}`,
              borderRadius: 8,
              fontSize: 14,
            }}
          />
        </label>
        {error ? (
          <div style={{ marginBottom: 12, color: palette.critical, fontSize: 13 }}>{error}</div>
        ) : null}
        <button
          type="submit"
          disabled={loading || !password.trim()}
          style={{
            width: "100%",
            padding: "10px 14px",
            borderRadius: 8,
            border: "none",
            background: loading ? palette.border : palette.caution,
            color: palette.text,
            fontSize: 14,
            fontWeight: 600,
            cursor: loading || !password.trim() ? "not-allowed" : "pointer",
            opacity: loading || !password.trim() ? 0.7 : 1,
          }}
        >
          {loading ? "확인 중..." : "관리자 로그인"}
        </button>
      </form>
    </div>
  );
}
