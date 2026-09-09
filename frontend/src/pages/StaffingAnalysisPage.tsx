import { useEffect, useMemo, useState } from "react";
import { BenchmarkTable, type BenchmarkRow } from "../components/analysis/BenchmarkTable";
import { StaffingHourlyChart } from "../components/charts/StaffingHourlyChart";
import { StaffingTrendChart } from "../components/charts/StaffingTrendChart";
import { PageState } from "../components/PageState";
import { buildStaffingTrendChartData } from "../lib/staffingTrendChartData";
import { compareToBenchmarkKey, TREND_OPTIONS } from "../lib/dashboardCompare";
import { formatThousandUnit } from "../lib/numberFormat";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { useRequestGeneration } from "../hooks/useRequestGeneration";
import { fetchStaffingAnalysis } from "../lib/api";
import type { StaffingAnalysis, StaffingBenchmark } from "../types/staffingAnalysis";

function formatMetric(value?: number | null, unit = "", decimals = 1) {
  if (value === null || value === undefined) return "-";
  const formatted = unit === "천" ? formatThousandUnit(value, decimals) : value.toFixed(decimals);
  return `${formatted}${unit}`;
}

function buildBenchmarkRows(summary: StaffingAnalysis["summary"], benchmark?: StaffingBenchmark): BenchmarkRow[] {
  return [
    {
      label: "인시당 처리량",
      current: summary.productivity,
      benchmark: benchmark?.productivity,
      unit: "개",
      decimals: 1,
      higherIsBetter: true,
    },
    {
      label: "평균 실근무",
      current: summary.avgStaff,
      benchmark: benchmark?.avgStaff,
      unit: "명",
      decimals: 1,
      higherIsBetter: false,
    },
    {
      label: "피크 실근무",
      current: summary.peakStaff,
      benchmark: benchmark?.peakStaff,
      unit: "명",
      decimals: 0,
      higherIsBetter: false,
    },
  ];
}

export default function StaffingAnalysisPage() {
  const { palette } = useTheme();
  const { selectedDate, compare, setCompareBasis, trendView, setVolumeTrendView } = useDashboardFilters();
  const { next, isCurrent, invalidate } = useRequestGeneration();
  const [data, setData] = useState<StaffingAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeBenchmarkKey = compareToBenchmarkKey(compare);

  const loadData = (date = selectedDate) => {
    if (!date) return;
    const requestId = next();
    setData(null);
    setLoading(true);
    setError(null);
    fetchStaffingAnalysis(date)
      .then((payload) => {
        if (!isCurrent(requestId)) return;
        setData(payload);
      })
      .catch(() => {
        if (!isCurrent(requestId)) return;
        setError("인력·생산성 데이터를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!isCurrent(requestId)) return;
        setLoading(false);
      });
  };

  useEffect(() => {
    if (!selectedDate) {
      setData(null);
      return;
    }
    loadData(selectedDate);
    return () => invalidate();
  }, [selectedDate]);

  const trendData = useMemo(() => {
    if (!data) return null;
    return data.trends?.[trendView] ?? data.dailyTrend;
  }, [data, trendView]);

  const trendTitle = TREND_OPTIONS.find((option) => option.value === trendView)?.label ?? "생산성 추세";
  const sharedTrendChartData = useMemo(() => {
    if (!trendData) return null;
    return buildStaffingTrendChartData(trendData, data?.meta.reportDate);
  }, [trendData, data?.meta.reportDate]);

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
    { label: "인시당 처리량", value: formatMetric(data.summary.productivity, "개"), accent: true },
    { label: "평균 실근무인력", value: formatMetric(data.summary.avgStaff, "명", 1) },
    { label: "피크 실근무인력", value: formatMetric(data.summary.peakStaff, "명", 0) },
    { label: "피크 시간대", value: data.summary.peakHour ?? "-" },
    { label: "피크 시간 물량", value: formatMetric(data.summary.peakHourVolume, "천", 1) },
    { label: "총 처리물량", value: formatMetric(data.summary.totalVolume, "천", 1) },
  ];

  return (
    <>
      <section className="imc-kpi-grid imc-kpi-grid--6">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            style={{
              ...panelStyle,
              ...(card.accent
                ? {
                    borderLeft: `4px solid ${palette.caution}`,
                  }
                : {}),
            }}
          >
            <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>{card.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, whiteSpace: "nowrap" }}>{card.value}</div>
          </div>
        ))}
      </section>

      <section style={{ display: "grid", gap: 16, marginBottom: 16 }}>
        <div style={panelStyle}>
          <h3 style={{ margin: "0 0 12px" }}>시간대별 처리물량 · 인력 · 생산성</h3>
          <StaffingHourlyChart hourly={data.hourly} />
        </div>

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
            <h3 style={{ margin: 0 }}>일별 생산성 추세</h3>
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
            <StaffingTrendChart
              data={trendData}
              referenceDate={data.meta.reportDate}
              chartData={sharedTrendChartData}
            />
          ) : null}
          <div style={{ marginTop: 8, color: palette.muted, fontSize: 12 }}>
            {trendView === "weekday"
              ? "최근 30업무일 이내 보고서 기준 요일별 평균 생산성입니다."
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
