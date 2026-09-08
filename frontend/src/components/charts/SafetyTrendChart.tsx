import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SafetyTrendSeries } from "../../types/safetyAnalysis";
import { useTheme } from "../../context/ThemeContext";
import {
  buildSafetyTrendChartData,
  getSafetyTrendXAxisProps,
  SAFETY_TREND_MARGIN_WITH_AXIS,
  type SafetyTrendChartPoint,
} from "../../lib/safetyTrendChartData";

type Props = {
  data: SafetyTrendSeries;
  referenceDate?: string;
  chartData?: SafetyTrendChartPoint[];
};

export function SafetyTrendChart({ data, referenceDate, chartData: chartDataProp }: Props) {
  const { palette } = useTheme();
  const isWeekdayMode = data.mode === "weekday";
  const chartData = chartDataProp ?? buildSafetyTrendChartData(data, referenceDate);

  return (
    <div style={{ height: 320, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={SAFETY_TREND_MARGIN_WITH_AXIS}>
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            stroke={palette.chartText}
            {...getSafetyTrendXAxisProps(chartData.length, isWeekdayMode, palette.chartText)}
          />
          <YAxis
            yAxisId="count"
            stroke={palette.chartText}
            allowDecimals={false}
            width={40}
            tick={{ fill: palette.chartText, fontSize: 11 }}
          />
          <YAxis
            yAxisId="rate"
            orientation="right"
            stroke={palette.chartText}
            domain={[0, 100]}
            width={48}
            tick={{ fill: palette.chartText, fontSize: 11 }}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            labelFormatter={(_, payload) => {
              const item = payload?.[0]?.payload as SafetyTrendChartPoint | undefined;
              if (!item) return "";
              return isWeekdayMode ? `${item.dateText}요일 평균 ${item.weekdayText}` : item.axisLabel;
            }}
            formatter={(value, name) => {
              if (name === "안전점검 양호율") return [`${Number(value ?? 0).toFixed(1)}%`, String(name)];
              return [`${value ?? 0}건`, String(name)];
            }}
          />
          <Legend />
          <Bar yAxisId="count" dataKey="incidentCount" name="재해" fill="#ef4444" radius={[4, 4, 0, 0]} maxBarSize={20} />
          <Bar yAxisId="count" dataKey="warningCount" name="주의 이상징후" fill="#f59e0b" radius={[4, 4, 0, 0]} maxBarSize={20} />
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="safetyPassRate"
            name="안전점검 양호율"
            stroke="#22c55e"
            strokeWidth={2}
            dot={{ r: 3, fill: "#22c55e", strokeWidth: 0 }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
