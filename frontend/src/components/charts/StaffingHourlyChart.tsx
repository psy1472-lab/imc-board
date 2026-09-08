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
import type { StaffingAnalysis } from "../../types/staffingAnalysis";
import { useTheme } from "../../context/ThemeContext";
import { formatHourLabel, HOUR_SLOTS } from "../../lib/hourSlots";
import {
  HOURLY_CHART_MARGIN,
  HOURLY_HIDDEN_Y_AXIS_WIDTH,
  HOURLY_STAFF_Y_AXIS_WIDTH,
  HOURLY_VOLUME_Y_AXIS_WIDTH,
} from "../../lib/hourlyChartLayout";
import { formatThousandUnit } from "../../lib/numberFormat";
import { HourlyChartUnitHeader } from "./HourlyChartUnitHeader";
import { HourlyYAxisTick } from "./HourlyYAxisTick";

type Props = {
  hourly: StaffingAnalysis["hourly"];
};

export function StaffingHourlyChart({ hourly }: Props) {
  const { palette } = useTheme();
  const chartData = HOUR_SLOTS.map((slot, index) => ({
    label: formatHourLabel(slot),
    volume: hourly.volume[index],
    staff: hourly.staff[index],
    productivity: hourly.productivity[index],
  }));

  return (
    <div className="imc-chart" style={{ height: 320, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <HourlyChartUnitHeader left="처리물량(천)" right="인력(명)" />
      <div style={{ flex: 1, minHeight: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={HOURLY_CHART_MARGIN} barCategoryGap="12%">
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            stroke={palette.chartText}
            interval={0}
            angle={-30}
            textAnchor="end"
            height={52}
            tickMargin={8}
            tick={{ fontSize: 11, fill: palette.chartText }}
          />
          <YAxis
            yAxisId="volume"
            stroke={palette.chartText}
            width={HOURLY_VOLUME_Y_AXIS_WIDTH}
            tick={(props) => (
              <HourlyYAxisTick
                {...props}
                fill={palette.chartText}
                orientation="left"
                text={`${formatThousandUnit(props.payload?.value, 0)}천`}
              />
            )}
          />
          <YAxis
            yAxisId="staff"
            orientation="right"
            stroke={palette.chartText}
            width={HOURLY_STAFF_Y_AXIS_WIDTH}
            allowDecimals={false}
            tick={(props) => (
              <HourlyYAxisTick
                {...props}
                fill={palette.chartText}
                orientation="right"
                text={`${props.payload?.value ?? ""}명`}
              />
            )}
          />
          <YAxis
            yAxisId="productivity"
            orientation="right"
            hide
            width={HOURLY_HIDDEN_Y_AXIS_WIDTH}
            domain={[0, "auto"]}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            formatter={(value, name) => {
              if (name === "처리물량") return [`${formatThousandUnit(value)}천`, String(name)];
              if (name === "실근무인력") return [`${value ?? "-"}명`, String(name)];
              return [`${Number(value ?? 0).toFixed(1)}개`, String(name)];
            }}
          />
          <Legend />
          <Bar
            yAxisId="volume"
            dataKey="volume"
            name="처리물량(천)"
            fill="#3b82f6"
            radius={[4, 4, 0, 0]}
            maxBarSize={28}
          />
          <Bar
            yAxisId="staff"
            dataKey="staff"
            name="실근무인력(명)"
            fill="#22c55e"
            radius={[4, 4, 0, 0]}
            maxBarSize={20}
          />
          <Line
            yAxisId="productivity"
            type="monotone"
            dataKey="productivity"
            name="인시당 처리량(개)"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={{ r: 3, fill: "#f59e0b", strokeWidth: 0 }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
