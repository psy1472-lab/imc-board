import { useTheme } from "../../context/ThemeContext";
import { severityColor, type ThemePalette } from "../../styles/theme";

type Props = {
  label: string;
  status?: "PASS" | "WARNING" | "FAIL" | "NORMAL" | "CRITICAL" | string;
  onClick?: () => void;
};

function badgeBackground(status: string | undefined, palette: ThemePalette) {
  if (status === "PASS" || status === "NORMAL") return palette.badgeNormalBg;
  const color = severityColor(status === "FAIL" ? "CRITICAL" : status, palette);
  return `${color}26`;
}

function resolveColor(status: string | undefined, palette: ThemePalette) {
  if (status === "PASS" || status === "NORMAL") return severityColor("NORMAL", palette);
  if (status === "FAIL") return severityColor("CRITICAL", palette);
  return severityColor(status ?? "WARNING", palette);
}

export function ValidationStatusBadge({ label, status = "PASS", onClick }: Props) {
  const { palette } = useTheme();
  const color = resolveColor(status, palette);
  const interactive = Boolean(onClick);

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!interactive}
      style={{
        background: badgeBackground(status, palette),
        color,
        border: `1px solid ${color}`,
        borderRadius: 999,
        padding: "5px 10px",
        fontWeight: 700,
        fontSize: 12,
        whiteSpace: "nowrap",
        cursor: interactive ? "pointer" : "default",
      }}
    >
      {label}
    </button>
  );
}
