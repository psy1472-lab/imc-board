import { useEffect, useMemo, useState } from "react";
import { BenchmarkTable, type BenchmarkRow } from "../components/analysis/BenchmarkTable";
import { TransportTrendChart } from "../components/charts/TransportTrendChart";
import { TransportOfficeTable } from "../components/tables/TransportOfficeTable";
import { PageState } from "../components/PageState";
import { buildTransportTrendChartData } from "../lib/transportTrendChartData";
import { compareToBenchmarkKey, TREND_OPTIONS } from "../lib/dashboardCompare";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { useRequestGeneration } from "../hooks/useRequestGeneration";
import { fetchTransportAnalysis } from "../lib/api";
import { formatNumber } from "../styles/theme";
import type { TransportAnalysis, TransportBenchmark } from "../types/transportAnalysis";

function formatMetric(value?: number | null, unit = "", decimals = 1) {
  if (value === null || value === undefined) return "-";
  const formatted = unit === "%" ? `${value.toFixed(decimals)}%` : `${formatNumber(value)}${unit}`;
  return formatted;
}

function formatVehicleQuotaSub(
  actual?: number | null,
  standard?: number | null,
  standardLabel = "쿼터기준",
) {
  const actualText = actual == null ? "-" : `${actual}대`;
  const standardText = standard == null ? "-" : `${standard}대`;
  return `차량수 ${actualText} / ${standardLabel} ${standardText}`;
}

function isOverQuota(actual?: number | null, standard?: number | null) {
  return actual != null && standard != null && actual > standard;
}

function buildBenchmarkRows(summary: TransportAnalysis["summary"], benchmark?: TransportBenchmark): BenchmarkRow[] {
  return [
    {
      label: "쿼터 준수율",
      current: summary.quarterComplianceRate,
      benchmark: benchmark?.quarterComplianceRate,
      unit: "%",
      decimals: 1,
      higherIsBetter: true,
    },
    {
      label: "교환 준수율",
      current: summary.exchangeComplianceRate,
      benchmark: benchmark?.exchangeComplianceRate,
      unit: "%",
      decimals: 1,
      higherIsBetter: true,
    },
    {
      label: "쿼터 초과 집중국",
      current: summary.overageOfficeCount,
      benchmark: benchmark?.overageOfficeCount,
      unit: "곳",
      decimals: 0,
      higherIsBetter: false,
    },
  ];
}

export default function TransportAnalysisPage() {
  const { palette } = useTheme();
  const { selectedDate, compare, setCompareBasis, trendView, setVolumeTrendView } = useDashboardFilters();
  const { next, isCurrent, invalidate } = useRequestGeneration();
  const [data, setData] = useState<TransportAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeBenchmarkKey = compareToBenchmarkKey(compare);

  const loadData = (date = selectedDate) => {
    if (!date) return;
    const requestId = next();
    setData(null);
    setLoading(true);
    setError(null);
    fetchTransportAnalysis(date)
      .then((payload) => {
        if (!isCurrent(requestId)) return;
        setData(payload);
      })
      .catch(() => {
        if (!isCurrent(requestId)) return;
        setError("운송 관제 데이터를 불러오지 못했습니다.");
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

  const trendTitle = TREND_OPTIONS.find((option) => option.value === trendView)?.label ?? "운송 추세";
  const sharedTrendChartData = useMemo(() => {
    if (!trendData) return null;
    return buildTransportTrendChartData(trendData, data?.meta.reportDate);
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

  const quarterOverQuota = isOverQuota(data.summary.quarterActual, data.summary.quarterStandard);
  const summaryCards = [
    {
      label: "쿼터 준수율",
      value: formatMetric(data.summary.quarterComplianceRate, "%"),
      sub: formatVehicleQuotaSub(data.summary.quarterActual, data.summary.quarterStandard, "쿼터기준"),
      accent: !quarterOverQuota,
      warning: quarterOverQuota,
    },
    {
      label: "교환 준수율",
      value: formatMetric(data.summary.exchangeComplianceRate, "%"),
      sub: formatVehicleQuotaSub(data.summary.exchangeActual, data.summary.exchangeStandard, "교환기준"),
    },
    {
      label: "교환 잔량",
      value: data.summary.exchangeRemaining === 0 ? "없음" : formatNumber(data.summary.exchangeRemaining),
    },
    {
      label: "쿼터 초과 집중국",
      value: `${data.summary.overageOfficeCount ?? 0}곳`,
      sub: `물량 ${formatNumber(data.summary.overageOfficeVolume ?? 0)}개`,
      warning: (data.summary.overageOfficeCount ?? 0) > 0,
    },
    {
      label: "지연(23시초과) 집중국",
      value: `${data.summary.delayedOfficeCount ?? 0}곳`,
      sub: `물량 ${formatNumber(data.summary.delayedOfficeVolume ?? 0)}개`,
      warning: (data.summary.delayedOfficeCount ?? 0) > 0,
    },
    {
      label: "총 집중국 물량",
      value: formatNumber(data.summary.totalOfficeVolume),
      sub: `${data.summary.officeCount ?? 0}개 집중국`,
    },
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
                ? { borderLeft: `4px solid ${palette.caution}` }
                : card.warning
                  ? { borderLeft: `4px solid ${palette.warning}` }
                  : {}),
            }}
          >
            <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>{card.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, whiteSpace: "nowrap" }}>{card.value}</div>
            {card.sub ? (
              <div
                style={{
                  color: "warning" in card && card.warning ? palette.warning : palette.muted,
                  fontSize: 12,
                  marginTop: 6,
                }}
              >
                {card.sub}
              </div>
            ) : null}
          </div>
        ))}
      </section>

      <section style={{ display: "grid", gap: 16, marginBottom: 16 }}>
        <div style={panelStyle}>
          <h3 style={{ margin: "0 0 12px" }}>집중국별 운송 현황</h3>
          <TransportOfficeTable offices={data.offices} highlightOverages />
        </div>

        {data.quotaOverages.length > 0 ? (
          <div style={{ ...panelStyle, borderLeft: `4px solid ${palette.warning}` }}>
            <h3 style={{ margin: "0 0 12px", color: palette.warning }}>쿼터 초과 집중국</h3>
            <TransportOfficeTable offices={data.quotaOverages} />
          </div>
        ) : null}

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
            <h3 style={{ margin: 0 }}>운송 준수 추세</h3>
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
            <TransportTrendChart
              data={trendData}
              referenceDate={data.meta.reportDate}
              chartData={sharedTrendChartData}
            />
          ) : null}
          <div style={{ marginTop: 8, color: palette.muted, fontSize: 12 }}>
            {trendView === "weekday"
              ? "최근 30업무일 이내 보고서 기준 요일별 평균 운송 준수율입니다."
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
