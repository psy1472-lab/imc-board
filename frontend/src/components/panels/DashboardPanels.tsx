import type { DashboardSummary } from "../../types/dashboard";
import { useTheme } from "../../context/ThemeContext";
import { formatNumber, severityColor } from "../../styles/theme";

type Props = {
  items: Array<{
    severity: string;
    category?: string;
    categoryLabel?: string;
    message: string;
  }>;
};

const SEVERITY_LABELS: Record<string, string> = {
  NORMAL: "정상",
  CAUTION: "관심",
  WARNING: "주의",
  CRITICAL: "위험",
};

export function AnomalyList({ items }: Props) {
  const { palette } = useTheme();

  if (items.length === 0) {
    return (
      <div
        style={{
          padding: "20px 16px",
          textAlign: "center",
          color: palette.muted,
          fontSize: 13,
          background: palette.panelAlt,
          borderRadius: 10,
          border: `1px dashed ${palette.border}`,
        }}
      >
        오늘 등록된 이상징후가 없습니다.
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {items.map((item, index) => (
        <div
          key={`${item.category ?? "item"}-${index}`}
          style={{
            background: palette.panelAlt,
            border: `1px solid ${palette.border}`,
            borderLeft: `4px solid ${severityColor(item.severity, palette)}`,
            borderRadius: 10,
            padding: "12px 14px",
          }}
        >
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4, fontSize: 12 }}>
            <span style={{ color: severityColor(item.severity, palette) }}>
              {SEVERITY_LABELS[item.severity] ?? item.severity}
            </span>
            {item.categoryLabel ? <span style={{ color: palette.muted }}>{item.categoryLabel}</span> : null}
          </div>
          <div>{item.message}</div>
        </div>
      ))}
    </div>
  );
}

type EquipmentProps = {
  equipment: DashboardSummary["equipment"];
};

export function EquipmentGaugePanel({ equipment }: EquipmentProps) {
  const { palette } = useTheme();
  const gauges = [
    { label: "구분율", value: equipment.sortingRate },
    { label: "IPS", value: equipment.ipsRate },
    { label: "Reject", value: equipment.rejectRate },
    { label: "숏컷", value: equipment.shortcutRate },
  ];

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
        {gauges.map((gauge) => (
          <div
            key={gauge.label}
            style={{
              background: palette.panelAlt,
              border: `1px solid ${palette.border}`,
              borderRadius: 12,
              padding: 14,
              textAlign: "center",
            }}
          >
            <div style={{ color: palette.muted, fontSize: 12 }}>{gauge.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, marginTop: 8 }}>
              {gauge.value ?? "-"}%
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, color: palette.muted, fontSize: 13 }}>
        <div>시간당 평균/피크: {formatNumber(equipment.avgThroughput)} / {formatNumber(equipment.peakThroughput)}</div>
        <div>미판독: {formatNumber(equipment.unreadCount)} ({equipment.unreadRate ?? "-"}%)</div>
      </div>
    </div>
  );
}

type TransportProps = {
  transport: DashboardSummary["transport"];
  quotaOverages: DashboardSummary["quotaOverages"];
};

type TransportCardProps = {
  label: string;
  data: DashboardSummary["transport"]["quarter"];
  standardLabel?: string;
  remaining?: boolean;
};

function formatVehicleQuotaLine(
  actual?: number | null,
  standard?: number | null,
  standardLabel = "쿼터기준",
) {
  const actualText = actual == null ? "-" : `${actual}대`;
  const standardText = standard == null ? "-" : `${standard}대`;
  return `차량수 ${actualText} / ${standardLabel} ${standardText}`;
}

function TransportCard({ label, data, standardLabel = "쿼터기준", remaining = false }: TransportCardProps) {
  const { palette } = useTheme();
  const overQuota = !remaining && data.actual != null && data.standard != null && data.actual > data.standard;

  return (
    <div
      style={{
        background: palette.panelAlt,
        border: `1px solid ${palette.border}`,
        borderRadius: 12,
        padding: 14,
      }}
    >
      <div style={{ color: palette.muted, fontSize: 12, whiteSpace: "nowrap" }}>{label}</div>
      <div style={{ fontSize: remaining ? 20 : 15, fontWeight: 700, marginTop: 8, lineHeight: 1.4 }}>
        {remaining
          ? data.actual === 0
            ? "없음"
            : (data.actual ?? "-")
          : formatVehicleQuotaLine(data.actual, data.standard, standardLabel)}
      </div>
      {remaining ? null : (
        <div
          style={{
            color: overQuota ? palette.warning : palette.normal,
            marginTop: 6,
            fontSize: 12,
          }}
        >
          준수율 {data.complianceRate ?? "-"}%
          {overQuota ? " · 쿼터기준 초과" : ""}
        </div>
      )}
    </div>
  );
}

export function TransportPanel({ transport, quotaOverages }: TransportProps) {
  const { palette } = useTheme();

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, minWidth: 0 }}>
        <TransportCard label="쿼터 운송" data={transport.quarter} standardLabel="쿼터기준" />
        <TransportCard label="교환 운송" data={transport.exchange} standardLabel="교환기준" />
        <TransportCard
          label="교환 잔량"
          remaining
          data={{
            actual: transport.exchangeRemaining,
            standard: 0,
            complianceRate: 100,
          }}
        />
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          집중국별 쿼터 발송 초과현황
          {quotaOverages.length > 0 ? (
            <span style={{ color: palette.warning, marginLeft: 8, fontSize: 12 }}>WARNING</span>
          ) : null}
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: palette.muted, textAlign: "left" }}>
              <th style={{ paddingBottom: 6 }}>집중국</th>
              <th style={{ textAlign: "center" }}>차량수(A)</th>
              <th style={{ textAlign: "center" }}>당일쿼터(B)</th>
              <th style={{ textAlign: "center" }}>최종도착</th>
              <th style={{ textAlign: "center" }}>상태</th>
            </tr>
          </thead>
          <tbody>
            {quotaOverages.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: "12px 0", color: palette.muted }}>
                  쿼터 초과 집중국 없음
                </td>
              </tr>
            ) : (
              quotaOverages.map((office) => (
                <tr key={office.office} style={{ borderTop: `1px solid ${palette.border}` }}>
                  <td style={{ padding: "8px 0" }}>{office.office}</td>
                  <td style={{ textAlign: "center" }}>{office.vehiclesActual ?? "-"}</td>
                  <td style={{ textAlign: "center" }}>{office.vehiclesQuota ?? "-"}</td>
                  <td style={{ textAlign: "center" }}>{office.arrivalTime ?? "-"}</td>
                  <td style={{ textAlign: "center", color: severityColor(office.status ?? undefined, palette) }}>
                    {office.status}
                    {office.difference != null && office.difference > 0 ? ` (+${office.difference})` : ""}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type SafetyProps = {
  safety: DashboardSummary["safety"];
  displayMode?: "summary" | "full";
};

function maskPersonalName(name: string) {
  const trimmed = name.trim();
  if (!trimmed) return trimmed;
  if (trimmed.length === 1) return "*";
  if (trimmed.length === 2) return `${trimmed[0]}*`;
  return `${trimmed[0]}${"*".repeat(trimmed.length - 2)}${trimmed[trimmed.length - 1]}`;
}

function formatIncidentNarrative(
  item: DashboardSummary["safety"]["incidents"][number],
  displayMode: "summary" | "full",
) {
  const text = item.description ?? item.summary ?? "재해경위 정보 없음";
  if (displayMode === "full" || text.length <= 60) {
    return text;
  }
  const trimmed = text.slice(0, 60);
  const lastSpace = trimmed.lastIndexOf(" ");
  return `${lastSpace > 0 ? trimmed.slice(0, lastSpace) : trimmed}…`;
}

export function SafetyCategoryGrid({ safety }: SafetyProps) {
  const { palette } = useTheme();

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10 }}>
      {safety.categories.map((item) => (
        <div
          key={item.key}
          style={{
            background: palette.panelAlt,
            border: `1px solid ${palette.border}`,
            borderRadius: 10,
            padding: "12px 8px",
            textAlign: "center",
            whiteSpace: "nowrap",
          }}
        >
          <div style={{ color: palette.muted, fontSize: 12 }}>{item.label}</div>
          <div style={{ marginTop: 8, color: palette.normal }}>
            {item.passed}/{item.total} 양호
          </div>
        </div>
      ))}
    </div>
  );
}

export function SafetyIncidentPanel({ safety, displayMode = "summary" }: SafetyProps) {
  const { palette } = useTheme();
  const incidentCount = safety.incidentCount ?? safety.incidents?.length ?? 0;
  const isFullDisplay = displayMode === "full";

  return (
    <div>
      <div
        style={{
          color: incidentCount > 0 ? palette.warning : palette.normal,
          fontWeight: 600,
          fontSize: 15,
        }}
      >
        안전사고 {incidentCount}건
      </div>
      {incidentCount > 0 ? (
        <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
          {safety.incidents.map((item, index) => (
            <div
              key={`${item.name ?? "incident"}-${index}`}
              style={{
                background: palette.panelAlt,
                border: `1px solid ${palette.border}`,
                borderLeft: `4px solid ${palette.warning}`,
                borderRadius: 8,
                padding: "10px 12px",
                fontSize: 12,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 4 }}>
                {[item.department, item.name ? `${maskPersonalName(item.name)}(${item.gender ?? ""})` : null, item.occurrenceTime]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
              <div
                style={{
                  color: palette.muted,
                  lineHeight: isFullDisplay ? 1.6 : 1.5,
                  whiteSpace: isFullDisplay ? "pre-wrap" : "nowrap",
                  wordBreak: isFullDisplay ? "break-word" : undefined,
                  overflow: isFullDisplay ? undefined : "hidden",
                  textOverflow: isFullDisplay ? undefined : "ellipsis",
                }}
              >
                {formatIncidentNarrative(item, displayMode)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ marginTop: 12, color: palette.muted, fontSize: 13 }}>재해 발생 없음</div>
      )}
    </div>
  );
}

export function SafetyCheckGrid({ safety }: SafetyProps) {
  return (
    <div>
      <SafetyCategoryGrid safety={safety} />
      <div style={{ marginTop: 16 }}>
        <SafetyIncidentPanel safety={safety} />
      </div>
    </div>
  );
}
