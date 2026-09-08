import type { ThemePalette } from "../styles/theme";

export function chartColors(palette: ThemePalette) {
  return {
    primary: palette.chartSeries.primary,
    secondary: palette.chartSeries.secondary,
    tertiary: palette.chartSeries.tertiary,
    quaternary: palette.chartSeries.quaternary,
    warning: palette.chartSeries.warning,
    critical: palette.critical,
    muted: palette.chartSeries.muted,
  };
}

export function formatChartTooltipValue(value: unknown, name: string, unit = "") {
  if (value === null || value === undefined || value === "") return ["-", name];
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return [String(value), name];
  if (unit === "%") return [`${num}%`, name];
  if (unit === "천") return [`${num.toLocaleString("ko-KR")}천`, name];
  return [num.toLocaleString("ko-KR"), name];
}
