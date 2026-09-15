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
import type { EquipmentTrendSeries } from "../../types/equipmentAnalysis";
import { useTheme } from "../../context/ThemeContext";
import {
  buildEquipmentTrendChartData,
  getEquipmentTrendXAxisProps,
  type EquipmentTrendChartPoint,
} from "../../lib/equipmentTrendChartData";
import { HourlyChartUnitHeader } from "./HourlyChartUnitHeader";

type Props = {
  data: EquipmentTrendSeries;
  referenceDate?: string;
  chartData?: EquipmentTrendChartPoint[];
  ipsTarget?: number | null;
};

const LEGEND = [
  { key: "ipsRate", label: "IPS", color: "#3b82f6", shape: "line" as const },
  { key: "sortingRate", label: "구분율", color: "#22c55e", shape: "line" as const },
  { key: "rejectRate", label: "Reject", color: "#ef4444", shape: "line" as const },
  { key: "unreadRate", label: "미판독", color: "#f59e0b", shape: "bar" as const },
] as const;

const QUALITY_TREND_MARGIN = {
  top: 32,
  right: 8,
  left: 8,
  bottom: 36,
} as const;

export function EquipmentTrendChart({ data, referenceDate, chartData: chartDataProp, ipsTarget }: Props) {
  const { palette } = useTheme();
  const isWeekdayMode = data.mode === "weekday";
  const chartData = chartDataProp ?? buildEquipmentTrendChartData(data, referenceDate);

  return (
    <div className="imc-chart" style={{ height: 320, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <HourlyChartUnitHeader left="품질(%)" right="미판독(%)" />
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={QUALITY_TREND_MARGIN} barCategoryGap="18%">
            <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
            <XAxis
              stroke={palette.chartText}
              {...getEquipmentTrendXAxisProps(chartData.length, isWeekdayMode, palette.chartText)}
            />
            <YAxis
              yAxisId="quality"
              stroke={palette.chartText}
              domain={[85, 100]}
              allowDataOverflow
              ticks={[85, 90, 95, 100]}
              width={56}
              tick={{ fill: palette.chartText, fontSize: 11 }}
              tickFormatter={(value) => `${value}%`}
            />
            <YAxis
              yAxisId="unread"
              orientation="right"
              stroke={palette.chartText}
              domain={[0, (dataMax: number) => Math.max(5, Math.ceil((dataMax || 0) * 1.2 * 10) / 10)]}
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
                const item = payload?.[0]?.payload as EquipmentTrendChartPoint | undefined;
                if (!item) return "";
                return isWeekdayMode ? `${item.dateText}요일 평균 ${item.weekdayText}` : item.axisLabel;
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
                  {LEGEND.map((item) => (
                    <li key={item.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <span
                        style={{
                          display: "inline-block",
                          width: 12,
                          height: item.shape === "bar" ? 12 : 3,
                          borderRadius: 2,
                          background: item.color,
                        }}
                      />
                      {item.label}
                      {item.key === "ipsRate" && ipsTarget ? (
                        <span style={{ color: palette.muted, fontSize: 11 }}>(목표 {ipsTarget}%)</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            />
            <Bar
              yAxisId="unread"
              dataKey="unreadRate"
              name="미판독"
              fill="#f59e0b"
              radius={[4, 4, 0, 0]}
              maxBarSize={24}
            />
            <Line
              yAxisId="quality"
              type="monotone"
              dataKey="ipsRate"
              name="IPS"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3, fill: "#3b82f6", strokeWidth: 0 }}
              connectNulls
            />
            <Line
              yAxisId="quality"
              type="monotone"
              dataKey="sortingRate"
              name="구분율"
              stroke="#22c55e"
              strokeWidth={2}
              dot={{ r: 3, fill: "#22c55e", strokeWidth: 0 }}
              connectNulls
            />
            <Line
              yAxisId="quality"
              type="monotone"
              dataKey="rejectRate"
              name="Reject"
              stroke="#ef4444"
              strokeWidth={2}
              dot={{ r: 3, fill: "#ef4444", strokeWidth: 0 }}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
