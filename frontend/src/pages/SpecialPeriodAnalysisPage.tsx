import { useEffect, useMemo, useState } from "react";
import { PageState } from "../components/PageState";
import { Panel } from "../components/layout/Panel";
import { SpecialPeriodCompareChart } from "../components/charts/SpecialPeriodCompareChart";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { useRequestGeneration } from "../hooks/useRequestGeneration";
import { fetchSpecialPeriodAnalysis } from "../lib/api";
import { chartColors } from "../lib/chartColors";
import { formatDateWithWeekday } from "../lib/dateFormat";
import { formatNumber } from "../styles/theme";
import { panelAltStyle } from "../styles/panel";
import type {
  SpecialPeriodAnalysis,
  SpecialPeriodKpiValue,
  SpecialPeriodMachineStreamPoint,
  SpecialPeriodOption,
  SpecialPeriodPoint,
} from "../types/specialPeriodAnalysis";

type MachineStream = "dispatch" | "arrival";
type MachineMetric = "volume" | "share";

const MACHINE_STREAM_OPTIONS: Array<{ value: MachineStream; label: string }> = [
  { value: "dispatch", label: "발송" },
  { value: "arrival", label: "도착" },
];

const MACHINE_METRIC_OPTIONS: Array<{ value: MachineMetric; label: string }> = [
  { value: "volume", label: "물량" },
  { value: "share", label: "점유비" },
];

function formatValue(value?: number | null, unit = "") {
  if (value === null || value === undefined) return "-";
  return `${formatNumber(value)}${unit}`;
}

function changeTrend(percent: number | null): "UP" | "DOWN" | "STABLE" | null {
  if (percent === null || percent === undefined) return null;
  if (percent > 0) return "UP";
  if (percent < 0) return "DOWN";
  return "STABLE";
}

function trendColor(trend: "UP" | "DOWN" | "STABLE", palette: { normal: string; critical: string; muted: string }) {
  if (trend === "UP") return palette.normal;
  if (trend === "DOWN") return palette.critical;
  return palette.muted;
}

function formatChange(percent: number | null) {
  if (percent === null || percent === undefined) return "전년 대비 -";
  const trend = changeTrend(percent);
  const arrow = trend === "DOWN" ? "▼" : trend === "UP" ? "▲" : "─";
  const sign = percent > 0 ? "+" : "";
  return `${arrow} 전년 대비 ${sign}${percent.toFixed(1)}%`;
}

function periodOptionLabel(period: SpecialPeriodOption) {
  return `${period.startDate} ~ ${period.endDate}`;
}

function FilterToggleGroup<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  const { palette } = useTheme();
  return (
    <div role="group" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            style={{
              padding: "7px 12px",
              background: active ? palette.panelAlt : palette.inputBg,
              color: active ? palette.text : palette.muted,
              border: `1px solid ${active ? palette.caution : palette.border}`,
              borderRadius: 8,
              fontSize: 13,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function KpiCard({
  label,
  kpi,
  unit,
}: {
  label: string;
  kpi?: SpecialPeriodKpiValue | null;
  unit: string;
}) {
  const { palette } = useTheme();
  const trend = changeTrend(kpi?.changePercent ?? null);
  return (
    <div style={panelAltStyle(palette)}>
      <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, whiteSpace: "nowrap" }}>
        {formatValue(kpi?.current ?? null, unit)}
      </div>
      <div
        style={{
          marginTop: 8,
          fontSize: 12,
          color: trend ? trendColor(trend, palette) : palette.muted,
        }}
      >
        {formatChange(kpi?.changePercent ?? null)}
      </div>
      <div style={{ marginTop: 4, fontSize: 12, color: palette.muted }}>
        전년 {formatValue(kpi?.prior ?? null, unit)}
      </div>
    </div>
  );
}

function toChartRows(series: SpecialPeriodPoint[]) {
  return series.map((point) => ({
    label: point.label,
    currentDate: point.currentDate,
    priorDate: point.priorDate,
    currentInPeriod: point.currentInPeriod,
    totalCurrent: point.volume.totalCurrent,
    totalPrior: point.volume.totalPrior,
    dispatchCurrent: point.volume.dispatchCurrent,
    dispatchPrior: point.volume.dispatchPrior,
    arrivalCurrent: point.volume.arrivalCurrent,
    arrivalPrior: point.volume.arrivalPrior,
    quotaActualCurrent: point.quota.actualCurrent,
    quotaActualPrior: point.quota.actualPrior,
  }));
}

function toMachineRows(series: SpecialPeriodPoint[], stream: MachineStream, metric: MachineMetric) {
  return series.map((point) => {
    const values = point.machineSorting[stream];
    const suffix = metric === "volume" ? "Volume" : "Share";
    return {
      label: point.label,
      currentDate: point.currentDate,
      priorDate: point.priorDate,
      currentInPeriod: point.currentInPeriod,
      deck1Current: values[`deck1${suffix}Current` as keyof SpecialPeriodMachineStreamPoint],
      deck1Prior: values[`deck1${suffix}Prior` as keyof SpecialPeriodMachineStreamPoint],
      deck2Current: values[`deck2${suffix}Current` as keyof SpecialPeriodMachineStreamPoint],
      deck2Prior: values[`deck2${suffix}Prior` as keyof SpecialPeriodMachineStreamPoint],
      deck3Current: values[`deck3${suffix}Current` as keyof SpecialPeriodMachineStreamPoint],
      deck3Prior: values[`deck3${suffix}Prior` as keyof SpecialPeriodMachineStreamPoint],
    };
  });
}

export default function SpecialPeriodAnalysisPage() {
  const { palette } = useTheme();
  const colors = chartColors(palette);
  const { selectedDate } = useDashboardFilters();
  const { next, isCurrent, invalidate } = useRequestGeneration();
  const [data, setData] = useState<SpecialPeriodAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null);
  const [machineStream, setMachineStream] = useState<MachineStream>("dispatch");
  const [machineMetric, setMachineMetric] = useState<MachineMetric>("volume");

  const loadByDate = (date: string) => {
    const requestId = next();
    setData(null);
    setLoading(true);
    setError(null);
    fetchSpecialPeriodAnalysis({ date })
      .then((payload) => {
        if (!isCurrent(requestId)) return;
        setData(payload);
        setSelectedPeriodId(payload.currentPeriod?.id ?? null);
      })
      .catch(() => {
        if (!isCurrent(requestId)) return;
        setError("특별소통기간 분석 데이터를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!isCurrent(requestId)) return;
        setLoading(false);
      });
  };

  const loadByPeriod = (periodId: number) => {
    const requestId = next();
    setData(null);
    setLoading(true);
    setError(null);
    fetchSpecialPeriodAnalysis({ periodId })
      .then((payload) => {
        if (!isCurrent(requestId)) return;
        setData(payload);
        setSelectedPeriodId(payload.currentPeriod?.id ?? periodId);
      })
      .catch(() => {
        if (!isCurrent(requestId)) return;
        setError("특별소통기간 분석 데이터를 불러오지 못했습니다.");
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
    loadByDate(selectedDate);
    return () => invalidate();
  }, [selectedDate]);

  const chartRows = useMemo(() => (data?.series ? toChartRows(data.series) : []), [data]);
  const machineRows = useMemo(
    () => (data?.series ? toMachineRows(data.series, machineStream, machineMetric) : []),
    [data, machineStream, machineMetric],
  );
  const periodStartLabel = data?.series.find((point) => point.currentInPeriod)?.label ?? null;
  const periodEndLabel =
    [...(data?.series ?? [])].reverse().find((point) => point.currentInPeriod)?.label ?? null;
  const periodOptions = data?.sameYearPeriods?.length ? data.sameYearPeriods : data?.availablePeriods ?? [];

  if (!selectedDate) {
    return <PageState empty />;
  }

  if (loading && !data) {
    return <PageState loading />;
  }

  if (error && !data) {
    return <PageState error={error} onRetry={() => loadByDate(selectedDate)} />;
  }

  if (!data || !data.currentPeriod || !data.kpi) {
    return (
      <PageState
        empty
        emptyTitle="등록된 특별소통기간이 없습니다"
        emptyDescription="시스템 관리 또는 보고서 화면에서 특별소통기간을 등록한 뒤 다시 확인해 주세요."
      />
    );
  }

  const current = data.currentPeriod;
  const prior = data.priorPeriod;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Panel
        title="특별소통기간분석"
        actions={
          periodOptions.length > 1 ? (
            <select
              value={selectedPeriodId ?? current.id}
              onChange={(event) => loadByPeriod(Number(event.target.value))}
              style={{
                padding: "7px 10px",
                background: palette.inputBg,
                color: palette.text,
                border: `1px solid ${palette.border}`,
                borderRadius: 8,
                fontSize: 13,
              }}
            >
              {periodOptions.map((period) => (
                <option key={period.id} value={period.id}>
                  {periodOptionLabel(period)}
                </option>
              ))}
            </select>
          ) : null
        }
      >
        <div style={{ display: "grid", gap: 8, color: palette.muted, fontSize: 13, lineHeight: 1.6 }}>
          <div>
            올해 기간 {formatDateWithWeekday(current.startDate)} ~ {formatDateWithWeekday(current.endDate)} (
            {current.lengthDays}일)
          </div>
          <div>
            비교 창 {formatDateWithWeekday(current.windowStart)} ~ {formatDateWithWeekday(current.windowEnd)} ·
            등록 기간 전후 1주일
          </div>
          {prior ? (
            <div>
              전년 기간 {formatDateWithWeekday(prior.startDate)} ~ {formatDateWithWeekday(prior.endDate)} (
              {prior.lengthDays}일) · 창 {formatDateWithWeekday(prior.windowStart)} ~{" "}
              {formatDateWithWeekday(prior.windowEnd)}
            </div>
          ) : null}
          <div>일별 값은 달력이 아니라 기간 시작일 기준 오프셋(D-7~)으로 맞춥니다. 비교 기준은 전년 특별소통기간입니다.</div>
        </div>
      </Panel>

      {data.priorMissing ? (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            border: `1px solid ${palette.warning}`,
            background: palette.panelAlt,
            color: palette.text,
            fontSize: 13,
          }}
        >
          {data.message ?? "전년 특별소통기간이 등록되지 않았습니다"}
        </div>
      ) : null}

      <section className="imc-kpi-grid imc-kpi-grid--6">
        <KpiCard label="총 처리물량" kpi={data.kpi.totalVolume} unit="천개" />
        <KpiCard label="발송물량" kpi={data.kpi.dispatchVolume} unit="천개" />
        <KpiCard label="도착물량" kpi={data.kpi.arrivalVolume} unit="천개" />
        <KpiCard label="쿼터 실제" kpi={data.kpi.quotaActual} unit="대" />
        <KpiCard label="쿼터 기준" kpi={data.kpi.quotaStandard} unit="대" />
        <KpiCard label="쿼터 준수율" kpi={data.kpi.quotaComplianceRate} unit="%" />
      </section>

      <section className="imc-kpi-grid imc-kpi-grid--6">
        <KpiCard label="발송 1단 점유비" kpi={data.kpi.machineShare.dispatch.deck1} unit="%" />
        <KpiCard label="발송 2단 점유비" kpi={data.kpi.machineShare.dispatch.deck2} unit="%" />
        <KpiCard label="발송 3단 점유비" kpi={data.kpi.machineShare.dispatch.deck3} unit="%" />
        <KpiCard label="도착 1단 점유비" kpi={data.kpi.machineShare.arrival.deck1} unit="%" />
        <KpiCard label="도착 2단 점유비" kpi={data.kpi.machineShare.arrival.deck2} unit="%" />
        <KpiCard label="도착 3단 점유비" kpi={data.kpi.machineShare.arrival.deck3} unit="%" />
      </section>

      <Panel title="일별 총 처리물량">
        <SpecialPeriodCompareChart
          data={chartRows}
          series={[
            { key: "totalCurrent", label: "올해", color: colors.primary },
            { key: "totalPrior", label: "전년", color: colors.warning, dashed: true },
          ]}
          unitLabel="물량(천개)"
          tooltipUnit="천"
          periodStartLabel={periodStartLabel}
          periodEndLabel={periodEndLabel}
        />
        <div style={{ marginTop: 8, color: palette.muted, fontSize: 12 }}>
          배경은 올해 등록 특별소통기간입니다. 보고서가 없는 날은 비워 둡니다.
        </div>
      </Panel>

      <Panel title="발송·도착 물량">
        <SpecialPeriodCompareChart
          data={chartRows}
          series={[
            { key: "dispatchCurrent", label: "올해 발송", color: colors.tertiary },
            { key: "dispatchPrior", label: "전년 발송", color: colors.tertiary, dashed: true },
            { key: "arrivalCurrent", label: "올해 도착", color: colors.primary },
            { key: "arrivalPrior", label: "전년 도착", color: colors.primary, dashed: true },
          ]}
          unitLabel="물량(천개)"
          tooltipUnit="천"
          periodStartLabel={periodStartLabel}
          periodEndLabel={periodEndLabel}
        />
      </Panel>

      <Panel title="쿼터 차량">
        <SpecialPeriodCompareChart
          data={chartRows}
          series={[
            { key: "quotaActualCurrent", label: "올해 실제", color: colors.primary },
            { key: "quotaActualPrior", label: "전년 실제", color: colors.warning, dashed: true },
          ]}
          unitLabel="대수(대)"
          tooltipUnit=""
          periodStartLabel={periodStartLabel}
          periodEndLabel={periodEndLabel}
          emptyText="쿼터 차량 데이터가 없습니다. 축약형 보고서는 비어 있을 수 있습니다."
        />
      </Panel>

      <Panel
        title="기계구분 1·2·3단"
        actions={
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <FilterToggleGroup value={machineStream} options={MACHINE_STREAM_OPTIONS} onChange={setMachineStream} />
            <FilterToggleGroup value={machineMetric} options={MACHINE_METRIC_OPTIONS} onChange={setMachineMetric} />
          </div>
        }
      >
        <SpecialPeriodCompareChart
          data={machineRows}
          series={[
            { key: "deck1Current", label: "올해 1단", color: colors.primary },
            { key: "deck1Prior", label: "전년 1단", color: colors.primary, dashed: true },
            { key: "deck2Current", label: "올해 2단", color: colors.secondary },
            { key: "deck2Prior", label: "전년 2단", color: colors.secondary, dashed: true },
            { key: "deck3Current", label: "올해 3단", color: colors.tertiary },
            { key: "deck3Prior", label: "전년 3단", color: colors.tertiary, dashed: true },
          ]}
          unitLabel={machineMetric === "share" ? "점유비(%)" : "물량(천개)"}
          tooltipUnit={machineMetric === "share" ? "%" : "천"}
          periodStartLabel={periodStartLabel}
          periodEndLabel={periodEndLabel}
          emptyText="기계구분 데이터가 없습니다. 축약형 보고서는 비어 있을 수 있습니다."
        />
      </Panel>
    </div>
  );
}
