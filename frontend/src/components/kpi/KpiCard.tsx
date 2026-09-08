import type { KpiItem } from "../../types/dashboard";
import { useTheme } from "../../context/ThemeContext";
import { StatusBadge } from "./StatusBadge";
import { formatNumber, severityColor } from "../../styles/theme";

type Props = {
  item: KpiItem;
};

const VOLUME_KEYS = new Set([
  "total_volume",
  "dispatch_volume",
  "arrival_volume",
  "remaining_volume",
  "national_volume",
]);

function toThousand(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return value;
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return value;
  return Math.round(num / 100) / 10;
}

function normalizeVolumeKpi(item: KpiItem): KpiItem {
  if (!VOLUME_KEYS.has(item.key) || item.unit === "천개") {
    return item;
  }

  return {
    ...item,
    value: (toThousand(item.value as number) ?? item.value) as KpiItem["value"],
    unit: "천개",
    compare: item.compare
      ? {
          ...item.compare,
          compareValue:
            item.compare.compareValue === null || item.compare.compareValue === undefined
              ? item.compare.compareValue
              : (toThousand(item.compare.compareValue) as number | null | undefined),
        }
      : item.compare,
  } satisfies KpiItem;
}

function formatKpiValue(value: KpiItem["value"], unit?: string) {
  if (value === null || value === undefined || value === "") return "-";
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return String(value);
  if (unit === "천개") {
    return Number.isInteger(num) ? num.toLocaleString("ko-KR") : num.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  }
  return formatNumber(value);
}

function formatCompareValue(item: KpiItem): string {
  const value = item.compare?.compareValue;
  if (value === null || value === undefined) return "";

  if (item.unit === "%") {
    return `${value}%`;
  }
  if (item.unit) {
    return `${formatKpiValue(value, item.unit)}${item.unit}`;
  }
  return formatNumber(value);
}

function buildCompareText(item: KpiItem): string | null {
  if (item.compare?.percent !== undefined && item.compare?.percent !== null) {
    const arrow = item.compare.trend === "DOWN" ? "▼" : "▲";
    const percentText = `${arrow} ${Math.abs(item.compare.percent).toFixed(1)}%`;
    const compareValueText = formatCompareValue(item);
    return compareValueText ? `${percentText} (${compareValueText})` : percentText;
  }
  return null;
}

export function KpiCard({ item }: Props) {
  const { palette, mode } = useTheme();
  const kpi = normalizeVolumeKpi(item);
  const compareText = buildCompareText(kpi);
  const isNationalVolume = kpi.key === "national_volume";

  const cardStyle = isNationalVolume
    ? {
        background:
          mode === "dark"
            ? "linear-gradient(145deg, #152a4a 0%, #121c2e 55%)"
            : "linear-gradient(145deg, #eff6ff 0%, #ffffff 55%)",
        border: `1px solid ${palette.caution}`,
        borderLeft: `4px solid ${palette.caution}`,
        boxShadow:
          mode === "dark"
            ? "0 0 0 1px rgba(59, 130, 246, 0.12), inset 0 1px 0 rgba(147, 197, 253, 0.08)"
            : "0 0 0 1px rgba(37, 99, 235, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.9)",
      }
    : {
        background: palette.panel,
        border: `1px solid ${palette.border}`,
        borderLeft: kpi.status ? `4px solid ${severityColor(kpi.status, palette)}` : undefined,
      };

  return (
    <div className="imc-kpi-card" style={cardStyle}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
          marginBottom: 8,
        }}
      >
        <div
          style={{
            color: isNationalVolume ? palette.caution : palette.muted,
            fontSize: 13,
            fontWeight: isNationalVolume ? 600 : 400,
          }}
        >
          {kpi.label}
        </div>
        <StatusBadge status={kpi.status} />
      </div>
      <div className="imc-kpi-card__value">
        {formatKpiValue(kpi.value, kpi.unit)}
        {kpi.unit ? <span style={{ fontSize: 14, marginLeft: 4 }}>{kpi.unit}</span> : null}
      </div>
      {compareText ? (
        <div
          className="imc-kpi-card__compare"
          style={{
            color: kpi.status ? severityColor(kpi.status, palette) : palette.normal,
          }}
        >
          {compareText}
        </div>
      ) : null}
    </div>
  );
}
