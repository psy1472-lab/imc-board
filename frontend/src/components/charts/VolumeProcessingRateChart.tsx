import {
  Bar,
  CartesianGrid,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { VolumeTrendSeries } from "../../types/volumeAnalysis";
import { useTheme } from "../../context/ThemeContext";
import {
  buildTrendChartData,
  getTrendXAxisProps,
  TREND_CHART_MARGIN_COMPACT,
  TREND_CHART_MARGIN_COMPACT_WITH_AXIS,
  TREND_SYNC_ID,
  TREND_Y_AXIS_WIDTH,
  type TrendChartPoint,
} from "../../lib/volumeTrendChartData";

type Props = {
  data: VolumeTrendSeries;
  referenceDate?: string;
  chartData?: TrendChartPoint[];
  hideXAxis?: boolean;
};

const RATE_LEGEND = [
  { key: "totalProcessingRate", label: "전체", color: "#3b82f6" },
  { key: "dispatchProcessingRate", label: "발송", color: "#22c55e" },
  { key: "arrivalProcessingRate", label: "도착", color: "#f59e0b" },
] as const;

function formatRateLabel(value: unknown) {
  const num = typeof value === "number" ? value : Number(value);
  if (!num || Number.isNaN(num)) return "";
  return `${num.toFixed(1)}%`;
}

function getRateDomain(chartData: TrendChartPoint[]): [number, number] {
  const values = chartData.flatMap((row) => [
    row.totalProcessingRate,
    row.dispatchProcessingRate,
    row.arrivalProcessingRate,
  ]).filter((value): value is number => value !== null && value !== undefined);

  if (!values.length) return [0, 100];

  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = Math.max((max - min) * 0.2, 1.5);
  return [Math.max(0, Math.floor((min - padding) * 10) / 10), Math.ceil((max + padding) * 10) / 10];
}

export function VolumeProcessingRateChart({
  data,
  referenceDate,
  chartData: chartDataProp,
  hideXAxis = false,
}: Props) {
  const { palette } = useTheme();
  const isWeekdayMode = data.mode === "weekday";
  const isMonthlyMode = data.mode === "monthly";
  const isCategoryMode = isWeekdayMode || isMonthlyMode;
  const chartData = chartDataProp ?? buildTrendChartData(data, referenceDate);
  const rateDomain = getRateDomain(chartData);

  return (
    <div style={{ height: hideXAxis ? 260 : 300, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={chartData}
          syncId={TREND_SYNC_ID}
          margin={hideXAxis ? TREND_CHART_MARGIN_COMPACT : TREND_CHART_MARGIN_COMPACT_WITH_AXIS}
          barCategoryGap="18%"
          barGap={2}
        >
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            stroke={palette.chartText}
            {...getTrendXAxisProps(
              chartData.length,
              isWeekdayMode,
              hideXAxis,
              palette.chartText,
              isMonthlyMode,
            )}
          />
          <YAxis yAxisId="volume" hide domain={[0, "auto"]} />
          <YAxis
            yAxisId="rate"
            stroke={palette.chartText}
            domain={rateDomain}
            width={TREND_Y_AXIS_WIDTH}
            tick={{ fill: palette.chartText, fontSize: 11 }}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            formatter={(value, name) => [`${Number(value ?? 0).toFixed(2)}%`, String(name)]}
          />
          <Legend
            content={() => (
              <ul
                style={{
                  display: "flex",
                  justifyContent: "center",
                  gap: 16,
                  padding: 0,
                  margin: 0,
                  listStyle: "none",
                  color: palette.text,
                  fontSize: 12,
                }}
              >
                {RATE_LEGEND.map((item) => (
                  <li key={item.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        display: "inline-block",
                        width: 12,
                        height: 3,
                        borderRadius: 2,
                        background: item.color,
                      }}
                    />
                    {item.label}
                  </li>
                ))}
              </ul>
            )}
          />
          <Bar
            yAxisId="volume"
            dataKey="totalVolume"
            fill="transparent"
            stroke="none"
            maxBarSize={isCategoryMode ? 36 : 24}
            isAnimationActive={false}
          />
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="totalProcessingRate"
            name="전체"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: "#3b82f6", strokeWidth: 0 }}
            connectNulls
          >
            <LabelList dataKey="totalProcessingRate" position="top" formatter={formatRateLabel} fill="#3b82f6" fontSize={10} />
          </Line>
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="dispatchProcessingRate"
            name="발송"
            stroke="#22c55e"
            strokeWidth={2}
            dot={{ r: 3, fill: "#22c55e", strokeWidth: 0 }}
            connectNulls
          >
            <LabelList dataKey="dispatchProcessingRate" position="top" formatter={formatRateLabel} fill="#22c55e" fontSize={10} />
          </Line>
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="arrivalProcessingRate"
            name="도착"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={{ r: 3, fill: "#f59e0b", strokeWidth: 0 }}
            connectNulls
          >
            <LabelList dataKey="arrivalProcessingRate" position="top" formatter={formatRateLabel} fill="#f59e0b" fontSize={10} />
          </Line>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
