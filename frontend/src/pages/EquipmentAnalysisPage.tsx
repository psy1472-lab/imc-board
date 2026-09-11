import { useEffect, useMemo, useState } from "react";
import { BenchmarkTable, type BenchmarkRow } from "../components/analysis/BenchmarkTable";
import { EquipmentThroughputChart } from "../components/charts/EquipmentThroughputChart";
import { EquipmentTrendChart } from "../components/charts/EquipmentTrendChart";
import { MachineSortingChart } from "../components/charts/MachineSortingChart";
import { PageState } from "../components/PageState";
import { buildEquipmentTrendChartData } from "../lib/equipmentTrendChartData";
import { compareToBenchmarkKey, TREND_OPTIONS } from "../lib/dashboardCompare";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { useRequestGeneration } from "../hooks/useRequestGeneration";
import { fetchEquipmentAnalysis } from "../lib/api";
import { formatNumber } from "../styles/theme";
import type { EquipmentAnalysis, EquipmentBenchmark, MachineSortingStream, MachineSortingTrendSeries } from "../types/equipmentAnalysis";

const MACHINE_STREAM_OPTIONS: Array<{ value: MachineSortingStream; label: string }> = [
  { value: "dispatch", label: "발송" },
  { value: "arrival", label: "도착" },
];

function emptyMachineStreamTrend(length: number): MachineSortingTrendSeries["dispatch"] {
  const empty = Array.from({ length }, () => null);
  return {
    deck1Volume: [...empty],
    deck2Volume: [...empty],
    deck3Volume: [...empty],
    deck1Share: [...empty],
    deck2Share: [...empty],
    deck3Share: [...empty],
  };
}

function machineSortingToTrend(
  machineSorting: EquipmentAnalysis["machineSorting"],
  reportDate: string,
): MachineSortingTrendSeries | null {
  if (!machineSorting) return null;
  const hasValue =
    (machineSorting.dispatch?.length ?? 0) > 0 || (machineSorting.arrival?.length ?? 0) > 0;
  if (!hasValue) return null;

  const toStream = (rows: NonNullable<EquipmentAnalysis["machineSorting"]>["dispatch"]) => {
    const payload = emptyMachineStreamTrend(1);
    for (const row of rows ?? []) {
      if (row.deck === 1) {
        payload.deck1Volume[0] = row.volume ?? null;
        payload.deck1Share[0] = row.shareRate ?? null;
      } else if (row.deck === 2) {
        payload.deck2Volume[0] = row.volume ?? null;
        payload.deck2Share[0] = row.shareRate ?? null;
      } else if (row.deck === 3) {
        payload.deck3Volume[0] = row.volume ?? null;
        payload.deck3Share[0] = row.shareRate ?? null;
      }
    }
    return payload;
  };

  return {
    reportDates: [reportDate],
    dates: [reportDate.slice(5)],
    dispatch: toStream(machineSorting.dispatch),
    arrival: toStream(machineSorting.arrival),
  };
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return `${value.toFixed(1)}%`;
}

function buildBenchmarkRows(summary: EquipmentAnalysis["summary"], benchmark?: EquipmentBenchmark): BenchmarkRow[] {
  return [
    {
      label: "IPS",
      current: summary.ipsRate,
      benchmark: benchmark?.ipsRate,
      unit: "%",
      decimals: 1,
      higherIsBetter: true,
    },
    {
      label: "구분율",
      current: summary.sortingRate,
      benchmark: benchmark?.sortingRate,
      unit: "%",
      decimals: 1,
      higherIsBetter: true,
    },
    {
      label: "Reject율",
      current: summary.rejectRate,
      benchmark: benchmark?.rejectRate,
      unit: "%",
      decimals: 1,
      higherIsBetter: false,
    },
    {
      label: "미판독율",
      current: summary.unreadRate,
      benchmark: benchmark?.unreadRate,
      unit: "%",
      decimals: 1,
      higherIsBetter: false,
    },
  ];
}

function statusForIps(value: number | null | undefined, target: number | null | undefined, palette: ReturnType<typeof useTheme>["palette"]) {
  if (value === null || value === undefined || target === null || target === undefined) return palette.muted;
  if (value >= target) return palette.normal;
  if (value >= target - 1) return palette.warning;
  return palette.critical;
}

export default function EquipmentAnalysisPage() {
  const { palette } = useTheme();
  const { selectedDate, compare, setCompareBasis, trendView, setVolumeTrendView } = useDashboardFilters();
  const { next, isCurrent, invalidate } = useRequestGeneration();
  const [data, setData] = useState<EquipmentAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [machineStream, setMachineStream] = useState<MachineSortingStream>("dispatch");
  const activeBenchmarkKey = compareToBenchmarkKey(compare);

  const loadData = (date = selectedDate) => {
    if (!date) return;
    const requestId = next();
    setData(null);
    setLoading(true);
    setError(null);
    fetchEquipmentAnalysis(date)
      .then((payload) => {
        if (!isCurrent(requestId)) return;
        setData(payload);
      })
      .catch(() => {
        if (!isCurrent(requestId)) return;
        setError("설비·구분기 데이터를 불러오지 못했습니다.");
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

  const trendTitle = TREND_OPTIONS.find((option) => option.value === trendView)?.label ?? "설비 추세";
  const sharedTrendChartData = useMemo(() => {
    if (!trendData) return null;
    return buildEquipmentTrendChartData(trendData, data?.meta.reportDate);
  }, [trendData, data?.meta.reportDate]);

  const machineSortingTrend = useMemo(() => {
    if (!data) return null;
    const series = data.machineSortingTrends?.[trendView];
    if (series && (series.mode === "weekday" || series.dates.length > 0)) {
      return series;
    }
    return machineSortingToTrend(data.machineSorting, data.meta.reportDate);
  }, [data, trendView]);

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

  const ipsColor = statusForIps(data.summary.ipsRate, data.summary.ipsTarget, palette);
  const summaryCards = [
    { label: "IPS", value: formatPercent(data.summary.ipsRate), accent: true, color: ipsColor },
    { label: "구분율", value: formatPercent(data.summary.sortingRate) },
    { label: "Reject율", value: formatPercent(data.summary.rejectRate) },
    { label: "숏컷율", value: formatPercent(data.summary.shortcutRate) },
    { label: "시간당 평균", value: formatNumber(data.summary.avgThroughput) },
    { label: "시간당 피크", value: formatNumber(data.summary.peakThroughput) },
    { label: "미판독", value: formatNumber(data.summary.unreadCount) },
    { label: "미판독율", value: formatPercent(data.summary.unreadRate) },
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
                    borderLeft: `4px solid ${card.color ?? palette.caution}`,
                  }
                : {}),
            }}
          >
            <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>{card.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, whiteSpace: "nowrap", color: card.color ?? palette.text }}>
              {card.value}
            </div>
            {card.label === "IPS" && data.summary.ipsTarget ? (
              <div style={{ color: palette.muted, fontSize: 12, marginTop: 6 }}>목표 {data.summary.ipsTarget}%</div>
            ) : null}
          </div>
        ))}
      </section>

      <section style={{ display: "grid", gap: 16, marginBottom: 16 }}>
        <div className="imc-analysis-2col">
          <div style={panelStyle}>
            <h3 style={{ margin: "0 0 12px" }}>공급·구분 현황</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
              <div style={{ background: palette.panelAlt, borderRadius: 12, padding: 14 }}>
                <div style={{ color: palette.muted, fontSize: 12 }}>총 공급수</div>
                <div style={{ fontSize: 22, fontWeight: 700, marginTop: 8 }}>{formatNumber(data.summary.totalSupply)}</div>
              </div>
              <div style={{ background: palette.panelAlt, borderRadius: 12, padding: 14 }}>
                <div style={{ color: palette.muted, fontSize: 12 }}>총 구분수</div>
                <div style={{ fontSize: 22, fontWeight: 700, marginTop: 8 }}>{formatNumber(data.summary.totalSorted)}</div>
              </div>
            </div>
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
              <h3 style={{ margin: 0 }}>처리량 추세</h3>
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
            {trendData ? <EquipmentThroughputChart data={trendData} referenceDate={data.meta.reportDate} /> : null}
          </div>
        </div>

        <div style={panelStyle}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              marginBottom: 12,
              flexWrap: "wrap",
            }}
          >
            <h3 style={{ margin: 0 }}>기계구분 처리현황</h3>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <select
                value={machineStream}
                onChange={(e) => setMachineStream(e.target.value as MachineSortingStream)}
                style={{
                  padding: "8px 12px",
                  background: palette.inputBg,
                  color: palette.text,
                  border: `1px solid ${palette.border}`,
                  borderRadius: 8,
                  fontSize: 13,
                }}
              >
                {MACHINE_STREAM_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
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
          </div>
          {machineSortingTrend ? (
            <MachineSortingChart
              data={machineSortingTrend}
              stream={machineStream}
              referenceDate={data.meta.reportDate}
            />
          ) : null}
          <div style={{ marginTop: 8, color: palette.muted, fontSize: 12 }}>
            {trendView === "weekday"
              ? "최근 30업무일 이내 기계구분 단별 값의 요일 평균입니다."
              : `${trendTitle} · 기계구분 단별 값이 있는 날짜만 표시됩니다.`}
          </div>
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
            <h3 style={{ margin: 0 }}>품질 지표 추세</h3>
            <span style={{ color: palette.muted, fontSize: 12 }}>{trendTitle}</span>
          </div>
          {trendData && sharedTrendChartData ? (
            <EquipmentTrendChart
              data={trendData}
              referenceDate={data.meta.reportDate}
              chartData={sharedTrendChartData}
              ipsTarget={data.summary.ipsTarget}
            />
          ) : null}
          <div style={{ marginTop: 8, color: palette.muted, fontSize: 12 }}>
            {trendView === "weekday"
              ? "최근 30업무일 이내 보고서 기준 요일별 평균 설비 지표입니다."
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
