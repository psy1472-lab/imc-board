import { useTheme } from "../../context/ThemeContext";
import { severityColor } from "../../styles/theme";

const STATUS_LABELS: Record<string, string> = {
  NORMAL: "정상",
  CAUTION: "관심",
  WARNING: "주의",
  CRITICAL: "위험",
};

type Props = {
  status?: string;
  size?: "sm" | "md";
};

export function StatusBadge({ status, size = "sm" }: Props) {
  const { palette } = useTheme();
  if (!status) return null;

  const color = severityColor(status, palette);
  const label = STATUS_LABELS[status] ?? status;

  return (
    <span
      style={{
        display: "inline-block",
        padding: size === "sm" ? "2px 8px" : "4px 10px",
        borderRadius: 999,
        fontSize: size === "sm" ? 11 : 12,
        fontWeight: 600,
        color,
        background: `${color}22`,
        border: `1px solid ${color}55`,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}
