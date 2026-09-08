import { useTheme } from "../../context/ThemeContext";
import { severityColor } from "../../styles/theme";

export type BenchmarkRow = {
  label: string;
  current?: number | null;
  benchmark?: number | null;
  unit?: string;
  higherIsBetter?: boolean;
  decimals?: number;
};

function computeChange(current?: number | null, benchmark?: number | null) {
  if (current === null || current === undefined || benchmark === null || benchmark === undefined || benchmark === 0) {
    return null;
  }
  const diff = current - benchmark;
  const percent = (diff / benchmark) * 100;
  const trend = diff > 0 ? "UP" : diff < 0 ? "DOWN" : "STABLE";
  return { diff, percent, trend };
}

function formatMetric(value?: number | null, unit = "천개", decimals = 1) {
  if (value === null || value === undefined) return "-";
  if (unit === "%") return `${value.toFixed(decimals)}%`;
  if (unit === "천개") {
    return `${value.toLocaleString("ko-KR", { maximumFractionDigits: decimals })}${unit}`;
  }
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: decimals })}${unit}`;
}

function formatChangeText(
  change: NonNullable<ReturnType<typeof computeChange>>,
  unit = "천개",
  decimals = 1,
  higherIsBetter = true,
) {
  const arrow = change.trend === "DOWN" ? "▼" : change.trend === "UP" ? "▲" : "─";
  const diffText =
    unit === "%"
      ? `${change.diff > 0 ? "+" : ""}${change.diff.toFixed(decimals)}%p`
      : `${change.diff > 0 ? "+" : ""}${change.diff.toLocaleString("ko-KR", { maximumFractionDigits: decimals })}${unit}`;
  const percentText = `${change.percent > 0 ? "+" : ""}${change.percent.toFixed(1)}%`;
  const isGood =
    change.trend === "STABLE" ||
    (higherIsBetter ? change.trend === "UP" : change.trend === "DOWN");
  return { text: `${arrow} ${diffText} (${percentText})`, isGood };
}

type Props = {
  title: string;
  subtitle?: string;
  rows: BenchmarkRow[];
  active?: boolean;
  onSelect?: () => void;
};

export function BenchmarkTable({ title, subtitle, rows, active = false, onSelect }: Props) {
  const { palette } = useTheme();

  return (
    <div
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (!onSelect) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      style={{
        background: active ? palette.panel : palette.panelAlt,
        border: `1px solid ${active ? palette.caution : palette.border}`,
        borderRadius: 12,
        padding: 14,
        boxShadow: active ? `0 0 0 1px ${palette.caution}` : undefined,
        cursor: onSelect ? "pointer" : "default",
      }}
    >
      <div
        style={{
          fontWeight: 600,
          marginBottom: subtitle ? 4 : 10,
          color: active ? palette.text : undefined,
          display: "flex",
          alignItems: "center",
          gap: 6,
          minWidth: 0,
        }}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</span>
        {active ? <span style={{ fontSize: 11, color: palette.caution, flexShrink: 0 }}>선택됨</span> : null}
      </div>
      {subtitle ? (
        <div style={{ fontSize: 12, color: palette.muted, marginBottom: 10 }}>{subtitle}</div>
      ) : null}
      <div style={{ display: "grid", gap: 8 }}>
        {rows.map((row) => {
          const unit = row.unit ?? "천개";
          const decimals = row.decimals ?? (unit === "%" ? 1 : unit === "천개" ? 1 : 0);
          const higherIsBetter = row.higherIsBetter ?? true;
          const change = computeChange(row.current, row.benchmark);
          const changeDisplay = change
            ? formatChangeText(change, unit, decimals, higherIsBetter)
            : null;

          return (
            <div
              key={row.label}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 8,
                fontSize: 13,
                alignItems: "baseline",
              }}
            >
              <span style={{ color: palette.muted, flexShrink: 0 }}>{row.label}</span>
              <div style={{ textAlign: "right", minWidth: 0 }}>
                <div style={{ fontWeight: 600, whiteSpace: "nowrap" }}>
                  {formatMetric(row.current, unit, decimals)}
                </div>
                {changeDisplay ? (
                  <div
                    style={{
                      fontSize: 11,
                      marginTop: 2,
                      color: changeDisplay.isGood ? palette.normal : palette.critical,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {changeDisplay.text}
                  </div>
                ) : row.benchmark !== null && row.benchmark !== undefined ? (
                  <div style={{ fontSize: 11, marginTop: 2, color: palette.muted }}>
                    기준 {formatMetric(row.benchmark, unit, decimals)}
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function statusLabel(status?: string) {
  switch (status) {
    case "NORMAL":
      return "정상";
    case "CAUTION":
      return "관심";
    case "WARNING":
      return "주의";
    case "CRITICAL":
      return "위험";
    default:
      return status ?? "-";
  }
}

export function statusBadgeColor(status?: string, palette?: ReturnType<typeof useTheme>["palette"]) {
  if (!palette) return undefined;
  return severityColor(status, palette);
}
