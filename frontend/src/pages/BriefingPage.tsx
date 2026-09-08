import { useEffect, useState } from "react";
import { PageState } from "../components/PageState";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { fetchDailyBriefing } from "../lib/api";
import { formatDateWithWeekday } from "../lib/dateFormat";
import { panelStyle } from "../styles/panel";
import { severityColor } from "../styles/theme";
import type { BriefingItem, BriefingSection, DailyBriefing } from "../types/briefing";

const SEVERITY_LABELS: Record<string, string> = {
  NORMAL: "적정",
  CAUTION: "관심",
  WARNING: "관리필요",
  CRITICAL: "위험",
  UNKNOWN: "미확인",
};

function formatItemValue(item: BriefingItem) {
  if (item.value === null || item.value === undefined || item.value === "") {
    return item.text ?? "-";
  }
  return item.unit ? `${item.value}${item.unit}` : String(item.value);
}

function StatusBadge({ status, label }: { status?: string; label?: string }) {
  const { palette } = useTheme();
  const resolvedStatus = status ?? "UNKNOWN";
  const text = label ?? SEVERITY_LABELS[resolvedStatus] ?? resolvedStatus;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 700,
        color: severityColor(resolvedStatus, palette),
        border: `1px solid ${severityColor(resolvedStatus, palette)}`,
        background: `${severityColor(resolvedStatus, palette)}14`,
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}

function buildItemDetail(item: BriefingItem) {
  const parts = [item.text, item.assessment].filter(
    (part): part is string => typeof part === "string" && part.trim().length > 0,
  );
  const uniqueParts = parts.filter((part, index) => parts.indexOf(part) === index);
  return uniqueParts.length ? uniqueParts.join(" ") : null;
}

function SectionCard({ section }: { section: BriefingSection }) {
  const { palette } = useTheme();

  return (
    <div
      style={{
        background: palette.panel,
        border: `1px solid ${palette.border}`,
        borderRadius: 14,
        padding: 16,
        borderLeft: `4px solid ${severityColor(section.overallStatus ?? "NORMAL", palette)}`,
        minWidth: 0,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 17 }}>{section.title}</h3>
          {section.assessment ? (
            <p style={{ margin: "8px 0 0", color: palette.muted, fontSize: 13, lineHeight: 1.5 }}>
              {section.assessment}
            </p>
          ) : null}
        </div>
        {section.overallLabel ? <StatusBadge status={section.overallStatus} label={section.overallLabel} /> : null}
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        {section.items.map((item) => {
          const detailText = buildItemDetail(item);

          return (
            <div
              key={item.label}
              style={{
                fontSize: 13,
                padding: "10px 12px",
                borderRadius: 10,
                background: palette.panelAlt,
                border: `1px solid ${palette.border}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10,
                  minWidth: 0,
                  flexWrap: "wrap",
                }}
              >
                <span style={{ color: palette.muted, fontSize: 12, whiteSpace: "nowrap", flexShrink: 0 }}>
                  {item.label}
                </span>
                <span style={{ fontWeight: 600, flex: "1 1 120px", minWidth: 0 }}>{formatItemValue(item)}</span>
                {item.statusLabel ? <StatusBadge status={item.status} label={item.statusLabel} /> : null}
              </div>
              {detailText ? (
                <div
                  style={{
                    color: palette.muted,
                    fontSize: 12,
                    marginTop: 6,
                    lineHeight: 1.65,
                    wordBreak: "keep-all",
                    overflowWrap: "break-word",
                  }}
                >
                  {detailText}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      {section.gaps && section.gaps.length > 0 ? (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px dashed ${palette.border}` }}>
          <div style={{ color: palette.muted, fontSize: 12, marginBottom: 6 }}>분석 보완 필요 항목</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: palette.muted, fontSize: 12, lineHeight: 1.6 }}>
            {section.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export default function BriefingPage() {
  const { palette, mode } = useTheme();
  const { selectedDate } = useDashboardFilters();
  const [data, setData] = useState<DailyBriefing | null>(null);
  const [loading, setLoading] = useState(false);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    if (!selectedDate) return;
    setLoading(true);
    setForecastLoading(true);
    setError(null);
    fetchDailyBriefing(selectedDate, "prev_day", "core")
      .then((core) => {
        setData({
          ...core,
          tomorrowOutlook: core.tomorrowOutlook ?? { title: "내일 전망", items: [] },
        });
        setLoading(false);
        return fetchDailyBriefing(selectedDate, "prev_day", "forecast");
      })
      .then((forecast) => {
        setData((current) =>
          current
            ? {
                ...current,
                tomorrowOutlook: forecast.tomorrowOutlook ?? { title: "내일 전망", items: [] },
              }
            : forecast as DailyBriefing,
        );
      })
      .catch(() => setError("AI 운영 브리핑을 불러오지 못했습니다."))
      .finally(() => {
        setLoading(false);
        setForecastLoading(false);
      });
  };

  useEffect(() => {
    if (!selectedDate) {
      setData(null);
      return;
    }
    loadData();
  }, [selectedDate]);

  const panel = panelStyle(palette);

  if (!selectedDate) {
    return <PageState empty />;
  }

  if (loading && !data) {
    return <PageState loading />;
  }

  if (error && !data) {
    return <PageState error={error} onRetry={loadData} />;
  }

  if (!data) {
    return <PageState empty />;
  }

  return (
    <>
      <div
        style={{
          ...panel,
          marginBottom: 16,
          background:
            mode === "dark"
              ? "linear-gradient(145deg, #152a4a 0%, #121c2e 55%)"
              : "linear-gradient(145deg, #eff6ff 0%, #ffffff 55%)",
          borderLeft: `4px solid ${palette.caution}`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <div style={{ color: palette.muted, fontSize: 13, marginBottom: 6 }}>AI 운영 브리핑</div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <h2 style={{ margin: 0, fontSize: 28 }}>{formatDateWithWeekday(data.meta.reportDate)}</h2>
            </div>
          </div>
          <div style={{ color: palette.muted, fontSize: 12, alignSelf: "flex-end" }}>
            규칙 기반 자동 생성
          </div>
        </div>
      </div>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${data.sections.todayOperation.items.length}, minmax(0, 1fr))`,
          gap: 12,
          marginBottom: 16,
        }}
      >
        {data.sections.todayOperation.items.map((item) => (
          <div key={item.label} style={panel}>
            <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>{item.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{formatItemValue(item)}</div>
          </div>
        ))}
      </section>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr)",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ ...panel, minWidth: 0 }}>
          <h3 style={{ margin: "0 0 12px" }}>{data.sections.majorChanges.title}</h3>
          {data.sections.majorChanges.items.length ? (
            <div style={{ display: "grid", gap: 10 }}>
              {data.sections.majorChanges.items.map((item) => (
                <div
                  key={item.label}
                  style={{
                    background: palette.panelAlt,
                    borderRadius: 10,
                    padding: "14px 16px",
                    borderLeft: `4px solid ${item.trend === "DOWN" ? palette.critical : item.trend === "UP" ? palette.normal : palette.muted}`,
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 14 }}>{item.label}</div>
                  <div
                    style={{
                      fontSize: 14,
                      lineHeight: 1.7,
                      color: palette.text,
                      wordBreak: "keep-all",
                      overflowWrap: "break-word",
                    }}
                  >
                    {item.text}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: palette.muted, fontSize: 13 }}>비교 가능한 주요 변화가 없습니다.</div>
          )}
        </div>

        <div style={{ ...panel, minWidth: 0 }}>
          <h3 style={{ margin: "0 0 12px" }}>주요 특이사항</h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: 10,
            }}
          >
            {data.highlights.map((item, index) => (
              <div
                key={`${item.category}-${index}`}
                style={{
                  background: palette.panelAlt,
                  border: `1px solid ${palette.border}`,
                  borderLeft: `4px solid ${severityColor(item.severity, palette)}`,
                  borderRadius: 10,
                  padding: "14px 16px",
                  minWidth: 0,
                }}
              >
                <div style={{ fontSize: 12, color: severityColor(item.severity, palette), marginBottom: 6 }}>
                  {SEVERITY_LABELS[item.severity] ?? item.severity}
                  {item.category ? ` · ${item.category}` : ""}
                </div>
                <div
                  style={{
                    fontSize: 14,
                    lineHeight: 1.65,
                    wordBreak: "keep-all",
                    overflowWrap: "break-word",
                  }}
                >
                  {item.message}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <SectionCard section={data.sections.staffing} />
        <SectionCard section={data.sections.transport} />
        <SectionCard section={data.sections.equipment} />
        <SectionCard section={data.sections.safety} />
      </section>

      <section style={{ ...panel, marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 12px" }}>{data.tomorrowOutlook?.title ?? "내일 전망"}</h3>
        {forecastLoading && (data.tomorrowOutlook?.items.length ?? 0) === 0 ? (
          <div style={{ color: palette.muted, fontSize: 13 }}>내일 전망을 계산하는 중입니다…</div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {data.tomorrowOutlook?.items.map((item) => (
              <div key={item.label} style={{ background: palette.panelAlt, borderRadius: 10, padding: "12px 14px" }}>
                <div style={{ color: palette.muted, fontSize: 12, marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 14, lineHeight: 1.6 }}>{item.text}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      {data.disclaimer ? (
        <footer style={{ color: palette.muted, fontSize: 12, lineHeight: 1.6 }}>{data.disclaimer}</footer>
      ) : null}
    </>
  );
}
