import { useLocation } from "react-router-dom";
import { NAV_ITEMS } from "../config/navigation";
import { useTheme } from "../context/ThemeContext";

export default function PlaceholderPage() {
  const { palette } = useTheme();
  const location = useLocation();
  const current = NAV_ITEMS.find((item) => item.path === location.pathname);

  return (
    <div
      style={{
        background: palette.panel,
        border: `1px solid ${palette.border}`,
        borderRadius: 14,
        padding: 32,
        color: palette.muted,
      }}
    >
      <h2 style={{ marginTop: 0, color: palette.text }}>{current?.label ?? "준비 중"}</h2>
      <p style={{ marginBottom: 0 }}>해당 화면은 다음 개발 단계에서 구현될 예정입니다.</p>
    </div>
  );
}
