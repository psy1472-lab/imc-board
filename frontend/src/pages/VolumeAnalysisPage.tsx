import { useEffect, useMemo, useState } from "react";
import { BenchmarkTable } from "../components/analysis/BenchmarkTable";
import { VolumeDailyTrendChart } from "../components/charts/VolumeDailyTrendChart";
import { VolumeProcessingRateChart } from "../components/charts/VolumeProcessingRateChart";
import { PageState } from "../components/PageState";
import { buildTrendChartData } from "../lib/volumeTrendChartData";
import {
  compareToBenchmarkKey,
  TREND_OPTIONS,
} from "../lib/dashboardCompare";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { formatDateWithWeekday } from "../lib/dateFormat";
import { fetchVolumeAnalysis } from "../lib/api";
import { formatDayType, isCompactReport } from "../lib/reportFormat";
import type { VolumeAnalysis } from "../types/volumeAnalysis";
function formatValue(value?: number | null, unit = "천개") {
  if (value === null || value === undefined) return "-";
  return `${value.toLocaleString("ko-KR")}${unit}`;
}

type BenchmarkRow = {
  label: string;
  current?: number | null;
  benchmark?: number | null;
};

function computeChange(current?: number | null, benchmark?: number | null) {
  if (current === null || current === undefined || benchmark === null || benchmark === undefined || benchmark === 0) {
    return null;
  }
  const diff = current - benchmark;
  const percent = (diff / benchmark) * 100;
  const trend: "UP" | "DOWN" | "STABLE" = diff > 0 ? "UP" : diff < 0 ? "DOWN" : "STABLE";
  return { diff, percent, trend };
}

function formatRatePointChange(current?: number | null, prior?: number | null) {
  if (current === null || current === undefined || prior === null || prior === undefined) {
    return null;
  }
  const diff = current - prior;
  const trend: "UP" | "DOWN" | "STABLE" = diff > 0 ? "UP" : diff < 0 ? "DOWN" : "STABLE";
  const arrow = trend === "DOWN" ? "▼" : trend === "UP" ? "▲" : "─";
  return {
    diff,
    trend,
    text: `${arrow} ${diff > 0 ? "+" : ""}${diff.toFixed(2)}%p`,
  };
}

function formatYearToDateChangeSuffix(current?: number | null, prior?: number | null) {
  const change = computeChange(current, prior);
  if (!change) return "";
  const diffText = `${change.diff > 0 ? "+" : ""}${change.diff.toLocaleString("ko-KR", {
    maximumFractionDigits: 1,
  })}천개`;
  const percentText = `${change.percent > 0 ? "+" : ""}${change.percent.toFixed(1)}%`;
  return ` (${diffText}, ${percentText})`;
}

function trendColor(trend: "UP" | "DOWN" | "STABLE", palette: { normal: string; critical: string; muted: string }) {
  if (trend === "UP") return palette.normal;
  if (trend === "DOWN") return palette.critical;
  return palette.muted;
}

type YearToDateViewMode = "cumulative" | "average";

const YEAR_TO_DATE_VIEW_OPTIONS: { value: YearToDateViewMode; label: string }[] = [
  { value: "cumulative", label: "연간누적물량" },
  { value: "average", label: "일평균" },
];

function YearToDateVolumeCard({
  label,
  priorLabel,
  value,
  prior,
  accent,
  mode,
}: {
  label: string;
  priorLabel: string;
  value?: number | null;
  prior?: number | null;
  accent?: boolean;
  mode: YearToDateViewMode;
}) {
  const { palette } = useTheme();
  const change = computeChange(value, prior);

  return (
    <div
      style={{
        background: palette.panelAlt,
        border: `1px solid ${accent ? palette.caution : palette.border}`,
        borderRadius: 12,
        padding: 14,
        ...(accent ? { borderLeft: `4px solid ${palette.caution}` } : {}),
      }}
    >
      <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>
        {label}
        {mode === "average" ? " 일평균" : ""}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, whiteSpace: "nowrap" }}>{formatValue(value)}</div>
      {prior !== null && prior !== undefined ? (
        <div
          style={{
            marginTop: 8,
            fontSize: 12,
            color: change ? trendColor(change.trend, palette) : palette.muted,
            whiteSpace: "nowrap",
          }}
        >
          {priorLabel} {formatValue(prior)}
          {formatYearToDateChangeSuffix(value, prior)}
        </div>
      ) : null}
    </div>
  );
}

function buildBenchmarkRows(
  summary: VolumeAnalysis["summary"],
  benchmark?: {
    totalVolume?: number | null;
    dispatchVolume?: number | null;
    arrivalVolume?: number | null;
  },
): BenchmarkRow[] {
  return [
    { label: "총 처리", current: summary.totalVolume, benchmark: benchmark?.totalVolume },
    { label: "발송", current: summary.dispatchVolume, benchmark: benchmark?.dispatchVolume },
    { label: "도착", current: summary.arrivalVolume, benchmark: benchmark?.arrivalVolume },
  ];
}

export default function VolumeAnalysisPage() {
  const { palette, mode } = useTheme();
  const { selectedDate, compare, setCompareBasis, trendView, setVolumeTrendView } = useDashboardFilters();
  const [data, setData] = useState<VolumeAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [yearToDateView, setYearToDateView] = useState<YearToDateViewMode>("cumulative");
  const activeBenchmarkKey = compareToBenchmarkKey(compare);

  const loadData = () => {
    if (!selectedDate) return;
    setLoading(true);
    setError(null);
    fetchVolumeAnalysis(selectedDate)
      .then(setData)
      .catch(() => setError("물량 분석 데이터를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!selectedDate) {
      setData(null);
      return;
    }
    loadData();
  }, [selectedDate]);

  const trendData = useMemo(() => {
    if (!data) return null;
    return data.trends?.[trendView] ?? data.dailyTrend;
  }, [data, trendView]);

  const trendTitle = TREND_OPTIONS.find((option) => option.value === trendView)?.label ?? "일별 물량 추세";
  const sharedTrendChartData = useMemo(() => {
    if (!trendData) return null;
    return buildTrendChartData(trendData, data?.meta.reportDate);
  }, [trendData, data?.meta.reportDate]);

  const monthlyTrendData = data?.monthlyTrend ?? null;
  const monthlyChartData = useMemo(() => {
    if (!monthlyTrendData) return null;
    return buildTrendChartData(monthlyTrendData, data?.meta.reportDate);
  }, [monthlyTrendData, data?.meta.reportDate]);
  const panelStyle = {
    background: palette.panel,
    border: `1px solid ${palette.border}`,
    borderRadius: 14,
    padding: 16,
  };

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

  const summaryCards = [
    { label: "전국접수물량", value: data.summary.nationalVolume, accent: true, naWhenCompact: true },
    { label: "총 처리물량", value: data.summary.totalVolume },
    { label: "발송물량", value: data.summary.dispatchVolume },
    {
      label: isCompactReport(data.meta.reportFormat) ? "배분물량" : "도착물량",
      value: data.summary.arrivalVolume,
    },
    { label: "잔량", value: data.summary.remainingVolume },
    {
      label: "전국대비처리율",
      value: data.summary.processingRate,
      unit: "%",
      disabledWhenNoNational: true,
    },
  ];

  const isCompact = isCompactReport(data.meta.reportFormat);

  return (
    <>
      {isCompact ? (
        <div
          style={{
            marginBottom: 16,
            padding: "10px 14px",
            borderRadius: 10,
            border: `1px solid ${palette.caution}`,
            background: palette.panelAlt,
            color: palette.muted,
            fontSize: 13,
          }}
        >
          주말·공휴일 축약형 보고서({formatDayType(data.meta.dayType)})입니다. 전국접수물량·처리율 등 일부
          항목은 PDF에 없을 수 있습니다.
        </div>
      ) : null}
      <section className="imc-kpi-grid imc-kpi-grid--6">
        {summaryCards.map((card) => {
          const showNa =
            (card.naWhenCompact && isCompact && (card.value === null || card.value === undefined)) ||
            (card.disabledWhenNoNational &&
              (data.summary.nationalVolume === null || data.summary.nationalVolume === undefined));
          return (
          <div
            key={card.label}
            style={{
              ...panelStyle,
              ...(card.accent
                ? {
                    background:
                      mode === "dark"
                        ? "linear-gradient(145deg, #152a4a 0%, #121c2e 55%)"
                        : "linear-gradient(145deg, #eff6ff 0%, #ffffff 55%)",
                    border: `1px solid ${palette.caution}`,
                    borderLeft: `4px solid ${palette.caution}`,
                    opacity: showNa ? 0.65 : 1,
                  }
                : {}),
            }}
          >
            <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>{card.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, whiteSpace: "nowrap" }}>
              {showNa
                ? "N/A"
                : card.unit === "%"
                  ? `${data.summary.processingRate ?? "-"}%`
                  : formatValue(card.value)}
            </div>
          </div>
          );
        })}
      </section>

      <section style={{ ...panelStyle, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0 }}>
                {data.yearToDate.year}년{" "}
                {yearToDateView === "cumulative" ? "연간누적물량" : "일평균 물량"}
              </h3>
              <select
                value={yearToDateView}
                onChange={(event) => setYearToDateView(event.target.value as YearToDateViewMode)}
                style={{
                  padding: "6px 10px",
                  background: palette.inputBg,
                  color: palette.text,
                  border: `1px solid ${palette.border}`,
                  borderRadius: 8,
                  fontSize: 13,
                }}
              >
                {YEAR_TO_DATE_VIEW_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ color: palette.muted, fontSize: 13 }}>
              {formatDateWithWeekday(data.yearToDate.startDate)} ~ {formatDateWithWeekday(data.yearToDate.endDate)} ·{" "}
              {data.yearToDate.dayCount}일 {yearToDateView === "cumulative" ? "누적" : "기준"}
            </div>
            {data.priorYearToDate ? (
              <div style={{ color: palette.muted, fontSize: 12, marginTop: 4 }}>
                전년 동기({formatDateWithWeekday(data.priorYearToDate.startDate)} ~{" "}
                {formatDateWithWeekday(data.priorYearToDate.endDate)} · {data.priorYearToDate.dayCount}일) 대비
              </div>
            ) : null}
          </div>
          {data.yearToDate.processingRate !== null && data.yearToDate.processingRate !== undefined ? (
            <div style={{ textAlign: "right" }}>
              <div style={{ color: palette.muted, fontSize: 12 }}>연간 누적 처리율</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{data.yearToDate.processingRate}%</div>
              {data.priorYearToDate ? (
                <div
                  style={{
                    marginTop: 6,
                    fontSize: 12,
                    color: (() => {
                      const change = formatRatePointChange(
                        data.yearToDate.processingRate,
                        data.priorYearToDate.processingRate,
                      );
                      return change ? trendColor(change.trend, palette) : palette.muted;
                    })(),
                  }}
                >
                  전년동기 처리율 {data.priorYearToDate.processingRate}%
                  {(() => {
                    const change = formatRatePointChange(
                      data.yearToDate.processingRate,
                      data.priorYearToDate.processingRate,
                    );
                    if (!change) return "";
                    const diffText = `${change.diff > 0 ? "+" : ""}${change.diff.toFixed(2)}%p`;
                    return ` (${diffText})`;
                  })()}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="imc-benchmark-grid">
          {[
            {
              label: "전국 접수물량",
              cumulative: data.yearToDate.nationalVolume,
              priorCumulative: data.priorYearToDate?.nationalVolume,
              average: data.yearToDate.avgNationalVolume,
              priorAverage: data.priorYearToDate?.avgNationalVolume,
              accent: true,
            },
            {
              label: "총 처리물량",
              cumulative: data.yearToDate.totalVolume,
              priorCumulative: data.priorYearToDate?.totalVolume,
              average: data.yearToDate.avgTotalVolume,
              priorAverage: data.priorYearToDate?.avgTotalVolume,
            },
            {
              label: "발송물량",
              cumulative: data.yearToDate.dispatchVolume,
              priorCumulative: data.priorYearToDate?.dispatchVolume,
              average: data.yearToDate.avgDispatchVolume,
              priorAverage: data.priorYearToDate?.avgDispatchVolume,
            },
            {
              label: "도착물량",
              cumulative: data.yearToDate.arrivalVolume,
              priorCumulative: data.priorYearToDate?.arrivalVolume,
              average: data.yearToDate.avgArrivalVolume,
              priorAverage: data.priorYearToDate?.avgArrivalVolume,
            },
          ].map((card) => (
            <YearToDateVolumeCard
              key={card.label}
              label={card.label}
              priorLabel="전년동기"
              value={yearToDateView === "cumulative" ? card.cumulative : card.average}
              prior={yearToDateView === "cumulative" ? card.priorCumulative : card.priorAverage}
              accent={card.accent}
              mode={yearToDateView}
            />
          ))}
        </div>
      </section>

      <section style={{ ...panelStyle, marginBottom: 20 }}>
        <h3 style={{ margin: "0 0 6px" }}>{data.yearToDate.year}년 월별 물량</h3>
        <div style={{ color: palette.muted, fontSize: 13, marginBottom: 12 }}>
          해당 연도 수집 보고서 기준 월별 누적 물량입니다.
        </div>
        {monthlyTrendData && monthlyChartData ? (
          <>
            <VolumeDailyTrendChart
              data={monthlyTrendData}
              referenceDate={data.meta.reportDate}
              chartData={monthlyChartData}
            />
            <div
              style={{
                marginTop: 4,
                paddingTop: 16,
                borderTop: `1px solid ${palette.border}`,
              }}
            >
              <h4 style={{ margin: "0 0 8px", fontSize: 15 }}>월별 전국접수물량 대비 처리율</h4>
              <VolumeProcessingRateChart
                data={monthlyTrendData}
                referenceDate={data.meta.reportDate}
                chartData={monthlyChartData}
              />
            </div>
          </>
        ) : (
          <div style={{ color: palette.muted }}>월별 물량 데이터가 없습니다.</div>
        )}
      </section>

      <section style={{ display: "grid", gap: 16, marginBottom: 16 }}>
        <div style={panelStyle}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              marginBottom: 12,
            }}
          >
            <h3 style={{ margin: 0 }}>일별 물량 추세</h3>
            <select
              value={trendView}
              onChange={(e) => setVolumeTrendView(e.target.value as typeof trendView)}
              style={{
                padding: "8px 12px",
                background: palette.inputBg,
                color: palette.text,
                border: `1px solid ${palette.border}`,
                borderRadius: 8,
                fontSize: 13,
              }}
            >
              {TREND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          {trendData && sharedTrendChartData ? (
            <>
              <VolumeDailyTrendChart
                data={trendData}
                referenceDate={data.meta.reportDate}
                chartData={sharedTrendChartData}
              />
              <div
                style={{
                  marginTop: 4,
                  paddingTop: 16,
                  borderTop: `1px solid ${palette.border}`,
                }}
              >
                <h4 style={{ margin: "0 0 8px", fontSize: 15 }}>전국접수물량 대비 처리율</h4>
                <VolumeProcessingRateChart
                  data={trendData}
                  referenceDate={data.meta.reportDate}
                  chartData={sharedTrendChartData}
                />
              </div>
            </>
          ) : null}
          <div style={{ marginTop: 8, color: palette.muted, fontSize: 12 }}>
            {trendView === "weekday"
              ? "최근 30업무일 이내 보고서 기준 요일별 평균 물량입니다."
              : `${trendTitle} · 보고서가 수집된 날짜만 표시됩니다.`}
          </div>
        </div>

        <div className="imc-benchmark-grid">
          <BenchmarkTable
            title="전일 대비 기준"
            rows={buildBenchmarkRows(data.summary, data.benchmarks.prevDay)}
            active={activeBenchmarkKey === "prevDay"}
            onSelect={() => setCompareBasis("prev_day")}
          />
          <BenchmarkTable
            title="최근 7업무일 평균"
            rows={buildBenchmarkRows(data.summary, data.benchmarks.avg7d)}
            active={activeBenchmarkKey === "avg7d"}
            onSelect={() => setCompareBasis("7d_avg")}
          />
          <BenchmarkTable
            title="최근 30업무일 평균"
            rows={buildBenchmarkRows(data.summary, data.benchmarks.avg30d)}
            active={activeBenchmarkKey === "avg30d"}
            onSelect={() => setCompareBasis("30d_avg")}
          />
          <BenchmarkTable
            title={`최근 30업무일 이내 동일 요일 평균(${data.benchmarks.sameWeekday?.weekdayLabel ?? "-"})`}
            rows={buildBenchmarkRows(data.summary, data.benchmarks.sameWeekday)}
            active={activeBenchmarkKey === "sameWeekday"}
            onSelect={() => setCompareBasis("same_weekday")}
          />
        </div>
      </section>

      <footer style={{ marginTop: 20, color: palette.muted, fontSize: 12 }}>
        데이터 갱신 기준: {data.meta.reportDate} · PDF 일일소통현황 보고서 기반
      </footer>
    </>
  );
}
