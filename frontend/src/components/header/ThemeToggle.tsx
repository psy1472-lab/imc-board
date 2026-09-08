import { useTheme } from "../../context/ThemeContext";

export function ThemeToggle() {
  const { mode, toggleMode, palette } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleMode}
      style={{
        background: palette.panelAlt,
        color: palette.text,
        border: `1px solid ${palette.border}`,
        borderRadius: 999,
        padding: "8px 14px",
        cursor: "pointer",
        fontWeight: 600,
      }}
    >
      {mode === "dark" ? "라이트 모드" : "다크 모드"}
    </button>
  );
}
