import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTheme } from "../../context/ThemeContext";
import { formatChartTooltipValue } from "../../lib/chartColors";
import { HourlyChartUnitHeader } from "./HourlyChartUnitHeader";
import { HourlyYAxisTick } from "./HourlyYAxisTick";
import { TREND_CHART_MARGIN_WITH_AXIS, TREND_Y_AXIS_WIDTH } from "../../lib/volumeTrendChartData";

export type CompareSeries = {
  key: string;
  label: string;
  color: string;
  dashed?: boolean;
};

type ChartRow = {
  label: string;
  currentDate: string | null;
  priorDate: string | null;
  currentInPeriod: boolean;
  [key: string]: string | number | boolean | null;
};

type Props = {
  data: ChartRow[];
  series: CompareSeries[];
  unitLabel: string;
  periodStartLabel?: string | null;
  periodEndLabel?: string | null;
  height?: number;
  emptyText?: string;
  tooltipUnit?: string;
};

function formatTick(value: unknown) {
  return String(value ?? "");
}

export function SpecialPeriodCompareChart({
  data,
  series,
  unitLabel,
  periodStartLabel,
  periodEndLabel,
  height = 320,
  emptyText = "비교할 데이터가 없습니다.",
  tooltipUnit = "",
}: Props) {
  const { palette } = useTheme();
  const hasValue = data.some((row) => series.some((item) => row[item.key] != null));
  const xInterval = data.length <= 12 ? 0 : Math.max(1, Math.ceil(data.length / 10) - 1);
  const rotateTicks = xInterval === 0 && data.length > 8;

  if (!hasValue) {
    return (
      <div style={{ color: palette.muted, fontSize: 13, padding: "28px 0" }}>{emptyText}</div>
    );
  }

  return (
    <div className="imc-chart" style={{ height, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <HourlyChartUnitHeader left={unitLabel} />
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={TREND_CHART_MARGIN_WITH_AXIS}>
            {periodStartLabel && periodEndLabel ? (
              <ReferenceArea
                x1={periodStartLabel}
                x2={periodEndLabel}
                fill={palette.caution}
                fillOpacity={0.1}
                ifOverflow="visible"
              />
            ) : null}
            <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
            <XAxis
              dataKey="label"
              stroke={palette.chartText}
              interval={xInterval}
              angle={rotateTicks ? -40 : 0}
              textAnchor={rotateTicks ? "end" : "middle"}
              height={rotateTicks ? 56 : 28}
              tick={{ fill: palette.chartText, fontSize: 11 }}
              tickFormatter={formatTick}
            />
            <YAxis
              stroke={palette.chartText}
              domain={[0, "auto"]}
              width={TREND_Y_AXIS_WIDTH}
              tick={(props) => (
                <HourlyYAxisTick
                  {...props}
                  fill={palette.chartText}
                  orientation="left"
                  text={
                    typeof props.payload?.value === "number"
                      ? props.payload.value.toLocaleString("ko-KR")
                      : String(props.payload?.value ?? "")
                  }
                />
              )}
            />
            <Tooltip
              contentStyle={{
                background: palette.panel,
                border: `1px solid ${palette.border}`,
                color: palette.text,
              }}
              labelFormatter={(_, payload) => {
                const row = payload?.[0]?.payload as ChartRow | undefined;
                if (!row) return "";
                const current = row.currentDate ? `올해 ${row.currentDate}` : "올해 없음";
                const prior = row.priorDate ? `전년 ${row.priorDate}` : "전년 없음";
                return `${row.label} · ${current} · ${prior}`;
              }}
              formatter={(value, name) => formatChartTooltipValue(value, String(name), tooltipUnit)}
            />
            <Legend />
            {series.map((item) => (
              <Line
                key={item.key}
                type="monotone"
                dataKey={item.key}
                name={item.label}
                stroke={item.color}
                strokeWidth={item.dashed ? 2.5 : 2.5}
                strokeDasharray={item.dashed ? "7 4" : undefined}
                dot={{
                  r: item.dashed ? 3 : 3,
                  fill: item.dashed ? palette.panel : item.color,
                  stroke: item.color,
                  strokeWidth: 1.5,
                }}
                connectNulls={false}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
