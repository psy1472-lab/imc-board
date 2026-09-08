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
import type { DashboardSummary } from "../../types/dashboard";
import { useTheme } from "../../context/ThemeContext";
import { chartColors } from "../../lib/chartColors";
import { buildHourlySeries, formatHourLabel, normalizeHourSlot } from "../../lib/hourSlots";
import {
  HOURLY_CHART_COMPACT_MARGIN,
  HOURLY_COUNT_Y_AXIS_WIDTH,
  HOURLY_STAFF_Y_AXIS_WIDTH,
} from "../../lib/hourlyChartLayout";
import { HourlyChartUnitHeader } from "./HourlyChartUnitHeader";
import { HourlyYAxisTick } from "./HourlyYAxisTick";

type Props = {
  staff: DashboardSummary["hourlyStaff"];
};

export function HourlyStaffChart({ staff }: Props) {
  const { palette } = useTheme();
  const colors = chartColors(palette);
  const chartData = buildHourlySeries(staff.actualStaff, (slot) => ({
    slot,
    label: formatHourLabel(slot),
    value: null,
  })).map((row) => {
    const productivity =
      staff.productivity.find((item) => normalizeHourSlot(item.slot) === normalizeHourSlot(row.slot))?.value ?? null;
    return {
      label: formatHourLabel(row.slot),
      actual: row.value ?? null,
      productivity,
    };
  });

  return (
    <div className="imc-chart" style={{ height: 280, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <HourlyChartUnitHeader left="인력(명)" right="인시당(개)" />
      <div style={{ flex: 1, minHeight: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={HOURLY_CHART_COMPACT_MARGIN}>
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            stroke={palette.chartText}
            interval={0}
            angle={-35}
            textAnchor="end"
            height={56}
            tickMargin={8}
            tick={{ fontSize: 11, fill: palette.chartText }}
          />
          <YAxis
            yAxisId="left"
            stroke={palette.chartText}
            domain={[0, "auto"]}
            allowDecimals={false}
            width={HOURLY_COUNT_Y_AXIS_WIDTH}
            tick={(props) => (
              <HourlyYAxisTick
                {...props}
                fill={palette.chartText}
                orientation="left"
                text={`${props.payload?.value ?? ""}명`}
              />
            )}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke={palette.chartText}
            domain={[0, "auto"]}
            width={HOURLY_STAFF_Y_AXIS_WIDTH}
            tick={(props) => (
              <HourlyYAxisTick
                {...props}
                fill={palette.chartText}
                orientation="right"
                text={`${props.payload?.value ?? ""}개`}
              />
            )}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
          />
          <Legend />
          <Bar yAxisId="left" dataKey="actual" name="실근무인력" fill={colors.tertiary} radius={[4, 4, 0, 0]} />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="productivity"
            name="인시당 처리량"
            stroke={colors.warning}
            dot={false}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
