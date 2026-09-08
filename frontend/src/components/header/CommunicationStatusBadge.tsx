import { useTheme } from "../../context/ThemeContext";
import { severityColor, type ThemePalette } from "../../styles/theme";

type Props = {
  label: string;
  status?: string;
  size?: "default" | "compact";
};

function badgeBackground(status: string | undefined, palette: ThemePalette) {
  if (status === "NORMAL") return palette.badgeNormalBg;
  const color = severityColor(status, palette);
  return `${color}26`;
}

export function CommunicationStatusBadge({ label, status = "NORMAL", size = "default" }: Props) {
  const { palette } = useTheme();
  const color = severityColor(status, palette);
  const compact = size === "compact";

  return (
    <div
      style={{
        background: badgeBackground(status, palette),
        color,
        border: `1px solid ${color}`,
        borderRadius: 999,
        padding: compact ? "2px 7px" : "8px 14px",
        fontWeight: 600,
        fontSize: compact ? 11 : 14,
        lineHeight: compact ? 1.3 : 1.4,
        whiteSpace: "nowrap",
        display: "inline-block",
        maxWidth: "100%",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {label}
    </div>
  );
}
