import {
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
  EQUIPMENT_TREND_MARGIN_WITH_AXIS,
  type EquipmentTrendChartPoint,
} from "../../lib/equipmentTrendChartData";

type Props = {
  data: EquipmentTrendSeries;
  referenceDate?: string;
  chartData?: EquipmentTrendChartPoint[];
  ipsTarget?: number | null;
};

const LEGEND = [
  { key: "ipsRate", label: "IPS", color: "#3b82f6" },
  { key: "sortingRate", label: "구분율", color: "#22c55e" },
  { key: "rejectRate", label: "Reject", color: "#ef4444" },
  { key: "unreadRate", label: "미판독", color: "#f59e0b" },
] as const;

export function EquipmentTrendChart({ data, referenceDate, chartData: chartDataProp, ipsTarget }: Props) {
  const { palette } = useTheme();
  const isWeekdayMode = data.mode === "weekday";
  const chartData = chartDataProp ?? buildEquipmentTrendChartData(data, referenceDate);

  return (
    <div style={{ height: 320, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={EQUIPMENT_TREND_MARGIN_WITH_AXIS}>
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            stroke={palette.chartText}
            {...getEquipmentTrendXAxisProps(chartData.length, isWeekdayMode, palette.chartText)}
          />
          <YAxis
            stroke={palette.chartText}
            domain={[85, 100]}
            width={56}
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
                        height: 3,
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
          <Line
            type="monotone"
            dataKey="ipsRate"
            name="IPS"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: "#3b82f6", strokeWidth: 0 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="sortingRate"
            name="구분율"
            stroke="#22c55e"
            strokeWidth={2}
            dot={{ r: 3, fill: "#22c55e", strokeWidth: 0 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="rejectRate"
            name="Reject"
            stroke="#ef4444"
            strokeWidth={2}
            dot={{ r: 3, fill: "#ef4444", strokeWidth: 0 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="unreadRate"
            name="미판독"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={{ r: 3, fill: "#f59e0b", strokeWidth: 0 }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
