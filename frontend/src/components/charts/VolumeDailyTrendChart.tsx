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
import { formatThousandUnit } from "../../lib/numberFormat";
import {
  buildTrendChartData,
  getTrendXAxisProps,
  TREND_CHART_MARGIN,
  TREND_CHART_MARGIN_WITH_AXIS,
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

const LEGEND = [
  { key: "totalVolume", label: "총 처리", color: "#3b82f6" },
  { key: "dispatchVolume", label: "발송", color: "#22c55e" },
  { key: "arrivalVolume", label: "도착", color: "#f59e0b" },
  { key: "nationalVolume", label: "전국접수", color: "#8b5cf6" },
] as const;

function formatBarLabel(value: unknown) {
  return formatThousandUnit(value);
}

export function VolumeDailyTrendChart({
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

  return (
    <div style={{ height: hideXAxis ? 300 : 360, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={chartData}
          syncId={TREND_SYNC_ID}
          margin={hideXAxis ? TREND_CHART_MARGIN : TREND_CHART_MARGIN_WITH_AXIS}
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
          <YAxis
            stroke={palette.chartText}
            allowDecimals={false}
            width={TREND_Y_AXIS_WIDTH}
            tick={{ fill: palette.chartText, fontSize: 11 }}
            tickFormatter={(value) => formatThousandUnit(value, 0)}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            labelFormatter={(_, payload) => {
              const item = payload?.[0]?.payload as TrendChartPoint | undefined;
              if (!item) return "";
              if (isMonthlyMode) return `${item.dateText} 누적 ${item.weekdayText}`;
              if (isWeekdayMode) return `${item.dateText}요일 평균 ${item.weekdayText}`;
              return item.axisLabel;
            }}
            formatter={(value, name) => [
              `${formatThousandUnit(value)}천`,
              String(name),
            ]}
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
                {LEGEND.map((item) => (
                  <li key={item.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        display: "inline-block",
                        width: 12,
                        height: item.key === "nationalVolume" ? 3 : 12,
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
          <Bar dataKey="totalVolume" name="총 처리" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={isCategoryMode ? 36 : 24}>
            <LabelList dataKey="totalVolume" position="top" formatter={formatBarLabel} fill={palette.text} fontSize={10} />
          </Bar>
          <Bar dataKey="dispatchVolume" name="발송" fill="#22c55e" radius={[4, 4, 0, 0]} maxBarSize={isCategoryMode ? 36 : 24}>
            <LabelList dataKey="dispatchVolume" position="top" formatter={formatBarLabel} fill={palette.text} fontSize={10} />
          </Bar>
          <Bar dataKey="arrivalVolume" name="도착" fill="#f59e0b" radius={[4, 4, 0, 0]} maxBarSize={isCategoryMode ? 36 : 24}>
            <LabelList dataKey="arrivalVolume" position="top" formatter={formatBarLabel} fill={palette.text} fontSize={10} />
          </Bar>
          <Line
            type="monotone"
            dataKey="nationalVolume"
            name="전국접수"
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={{ r: 3, fill: "#8b5cf6", strokeWidth: 0 }}
            connectNulls
          >
            <LabelList
              dataKey="nationalVolume"
              position="top"
              offset={10}
              formatter={formatBarLabel}
              fill="#a78bfa"
              fontSize={10}
            />
          </Line>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
