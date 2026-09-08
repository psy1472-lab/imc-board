export type ThemeMode = "dark" | "light";

export type ThemePalette = {
  bg: string;
  sidebar: string;
  panel: string;
  panelAlt: string;
  border: string;
  text: string;
  muted: string;
  normal: string;
  caution: string;
  warning: string;
  critical: string;
  chartGrid: string;
  chartText: string;
  inputBg: string;
  badgeNormalBg: string;
  chartSeries: {
    primary: string;
    secondary: string;
    tertiary: string;
    quaternary: string;
    warning: string;
    muted: string;
  };
};

export const darkPalette: ThemePalette = {
  bg: "#0b1220",
  sidebar: "#09111f",
  panel: "#121c2e",
  panelAlt: "#17233a",
  border: "#24324d",
  text: "#e8eefc",
  muted: "#9fb0d0",
  normal: "#22c55e",
  caution: "#3b82f6",
  warning: "#eab308",
  critical: "#ef4444",
  chartGrid: "#24324d",
  chartText: "#9fb0d0",
  inputBg: "#121c2e",
  badgeNormalBg: "rgba(34,197,94,0.15)",
  chartSeries: {
    primary: "#3b82f6",
    secondary: "#22d3ee",
    tertiary: "#22c55e",
    quaternary: "#eab308",
    warning: "#f97316",
    muted: "#94a3b8",
  },
};

export const lightPalette: ThemePalette = {
  bg: "#f3f6fb",
  sidebar: "#e9eef5",
  panel: "#ffffff",
  panelAlt: "#f8fafc",
  border: "#d7e0ea",
  text: "#0f172a",
  muted: "#64748b",
  normal: "#16a34a",
  caution: "#2563eb",
  warning: "#ca8a04",
  critical: "#dc2626",
  chartGrid: "#e2e8f0",
  chartText: "#64748b",
  inputBg: "#ffffff",
  badgeNormalBg: "rgba(22,163,74,0.12)",
  chartSeries: {
    primary: "#2563eb",
    secondary: "#0891b2",
    tertiary: "#16a34a",
    quaternary: "#ca8a04",
    warning: "#ea580c",
    muted: "#94a3b8",
  },
};

export function severityColor(severity: string | undefined, palette: ThemePalette) {
  switch (severity) {
    case "NORMAL":
      return palette.normal;
    case "CAUTION":
      return palette.caution;
    case "WARNING":
      return palette.warning;
    case "CRITICAL":
      return palette.critical;
    default:
      return palette.muted;
  }
}

export function formatNumber(value?: number | string | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString("ko-KR");
}
