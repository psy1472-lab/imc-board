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

const LOWER_IS_BETTER = new Set(["remaining_volume"]);

function toThousand(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return value;
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return value;
  return Math.round(num / 100) / 10;
}

function toNumeric(value: KpiItem["value"] | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const num = typeof value === "string" ? Number(value) : value;
  return Number.isNaN(num) ? null : num;
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
          difference:
            item.compare.difference === null || item.compare.difference === undefined
              ? item.compare.difference
              : (toThousand(item.compare.difference) as number | null | undefined),
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

function formatSignedValue(value: number, unit?: string) {
  const sign = value > 0 ? "+" : "";
  if (unit === "%") {
    return `${sign}${value.toFixed(1)}%p`;
  }
  if (unit === "천개") {
    const formatted = Number.isInteger(value)
      ? value.toLocaleString("ko-KR")
      : value.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
    return `${sign}${formatted}${unit}`;
  }
  const formatted = value.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  return `${sign}${formatted}${unit ?? ""}`;
}

function buildCompareText(item: KpiItem): string | null {
  const compare = item.compare;
  if (!compare) return null;

  const current = toNumeric(item.value);
  const prior = toNumeric(compare.compareValue);
  const diff = current !== null && prior !== null ? current - prior : toNumeric(compare.difference);
  const trend = compare.trend ?? (diff !== null ? (diff > 0 ? "UP" : diff < 0 ? "DOWN" : "STABLE") : undefined);
  const arrow = trend === "DOWN" ? "▼" : trend === "UP" ? "▲" : "─";

  if (diff === null) {
    if (compare.percent === undefined || compare.percent === null) return null;
    const percent = Number(compare.percent);
    return `${arrow} ${percent > 0 ? "+" : ""}${percent.toFixed(1)}%`;
  }

  const diffText = formatSignedValue(diff, item.unit);
  if (prior === 0 || compare.percent === undefined || compare.percent === null) {
    return `${arrow} ${diffText}`;
  }
  const percent = Number(compare.percent);
  const percentText = `${percent > 0 ? "+" : ""}${percent.toFixed(1)}%`;
  return `${arrow} ${diffText} (${percentText})`;
}

function compareIsFavorable(item: KpiItem): boolean {
  const trend = item.compare?.trend;
  if (!trend || trend === "STABLE") return true;
  const higherIsBetter = !LOWER_IS_BETTER.has(item.key);
  return higherIsBetter ? trend === "UP" : trend === "DOWN";
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
            color: compareIsFavorable(kpi) ? palette.normal : palette.critical,
          }}
        >
          {compareText}
        </div>
      ) : null}
    </div>
  );
}
