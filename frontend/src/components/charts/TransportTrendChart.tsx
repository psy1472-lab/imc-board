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
import type { TransportTrendSeries } from "../../types/transportAnalysis";
import { useTheme } from "../../context/ThemeContext";
import {
  buildTransportTrendChartData,
  getTransportTrendXAxisProps,
  TRANSPORT_TREND_MARGIN_WITH_AXIS,
  type TransportTrendChartPoint,
} from "../../lib/transportTrendChartData";

type Props = {
  data: TransportTrendSeries;
  referenceDate?: string;
  chartData?: TransportTrendChartPoint[];
};

const LEGEND = [
  { key: "quarterComplianceRate", label: "쿼터 준수율", color: "#3b82f6" },
  { key: "exchangeComplianceRate", label: "교환 준수율", color: "#22c55e" },
  { key: "overageOfficeCount", label: "쿼터 초과 집중국", color: "#f59e0b" },
] as const;

export function TransportTrendChart({ data, referenceDate, chartData: chartDataProp }: Props) {
  const { palette } = useTheme();
  const isWeekdayMode = data.mode === "weekday";
  const chartData = chartDataProp ?? buildTransportTrendChartData(data, referenceDate);

  return (
    <div style={{ height: 320, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={TRANSPORT_TREND_MARGIN_WITH_AXIS}>
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            stroke={palette.chartText}
            {...getTransportTrendXAxisProps(chartData.length, isWeekdayMode, palette.chartText)}
          />
          <YAxis
            yAxisId="rate"
            stroke={palette.chartText}
            domain={[0, 120]}
            width={56}
            tick={{ fill: palette.chartText, fontSize: 11 }}
            tickFormatter={(value) => `${value}%`}
          />
          <YAxis
            yAxisId="count"
            orientation="right"
            stroke={palette.chartText}
            allowDecimals={false}
            width={40}
            tick={{ fill: palette.chartText, fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            labelFormatter={(_, payload) => {
              const item = payload?.[0]?.payload as TransportTrendChartPoint | undefined;
              if (!item) return "";
              return isWeekdayMode ? `${item.dateText}요일 평균 ${item.weekdayText}` : item.axisLabel;
            }}
            formatter={(value, name) => {
              if (name === "쿼터 초과 집중국") return [`${value ?? 0}곳`, String(name)];
              return [`${Number(value ?? 0).toFixed(1)}%`, String(name)];
            }}
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
                        height: item.key === "overageOfficeCount" ? 12 : 3,
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
            yAxisId="count"
            dataKey="overageOfficeCount"
            name="쿼터 초과 집중국"
            fill="#f59e0b"
            radius={[4, 4, 0, 0]}
            maxBarSize={24}
          />
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="quarterComplianceRate"
            name="쿼터 준수율"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: "#3b82f6", strokeWidth: 0 }}
            connectNulls
          />
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="exchangeComplianceRate"
            name="교환 준수율"
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
