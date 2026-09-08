import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardSummary } from "../../types/dashboard";
import { useTheme } from "../../context/ThemeContext";
import { buildHourlySeries, formatHourLabel } from "../../lib/hourSlots";
import {
  HOURLY_CHART_COMPACT_MARGIN,
  HOURLY_VOLUME_Y_AXIS_WIDTH,
} from "../../lib/hourlyChartLayout";
import { HourlyChartUnitHeader } from "./HourlyChartUnitHeader";
import { HourlyYAxisTick } from "./HourlyYAxisTick";

type Props = {
  data: DashboardSummary["hourlyVolume"];
};

export function HourlyVolumeChart({ data }: Props) {
  const { palette } = useTheme();
  const volumeLegend = [
    { key: "dispatch", label: "발송(천)", color: palette.chartSeries.primary },
    { key: "arrival", label: "도착(천)", color: palette.chartSeries.secondary },
  ] as const;
  const chartData = buildHourlySeries(data.current, (slot) => ({
    slot,
    label: formatHourLabel(slot),
    dispatch: 0,
    arrival: 0,
  })).map((row) => ({
    label: formatHourLabel(row.slot),
    dispatch: (row.dispatch ?? 0) / 1000,
    arrival: (row.arrival ?? 0) / 1000,
  }));

  return (
    <div className="imc-chart" style={{ height: 280, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <HourlyChartUnitHeader left="처리물량(천)" />
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
            stroke={palette.chartText}
            domain={[0, "auto"]}
            width={HOURLY_VOLUME_Y_AXIS_WIDTH}
            tick={(props) => (
              <HourlyYAxisTick
                {...props}
                fill={palette.chartText}
                orientation="left"
                text={`${props.payload?.value ?? ""}천`}
              />
            )}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            formatter={(value, name) => {
              const num = typeof value === "number" ? value : Number(value);
              return [`${num.toLocaleString("ko-KR")}천`, name];
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
                }}
              >
                {volumeLegend.map((item) => (
                  <li key={item.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        display: "inline-block",
                        width: 12,
                        height: 12,
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
          <Bar dataKey="dispatch" name="발송(천)" stackId="volume" fill={palette.chartSeries.primary} radius={[0, 0, 0, 0]} />
          <Bar dataKey="arrival" name="도착(천)" stackId="volume" fill={palette.chartSeries.secondary} radius={[4, 4, 0, 0]} />
        </ComposedChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
