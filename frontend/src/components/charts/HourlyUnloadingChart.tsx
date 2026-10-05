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
  HOURLY_COUNT_Y_AXIS_WIDTH,
} from "../../lib/hourlyChartLayout";
import { HourlyChartUnitHeader } from "./HourlyChartUnitHeader";
import { HourlyYAxisTick } from "./HourlyYAxisTick";

type Props = {
  data?: DashboardSummary["hourlyUnloading"];
};

const SERIES = [
  { key: "collection", label: "수집" },
  { key: "quota", label: "쿼터" },
  { key: "arrival", label: "도착" },
  { key: "exchange", label: "교환" },
] as const;

export function HourlyUnloadingChart({ data }: Props) {
  const { palette } = useTheme();
  const colors = {
    collection: palette.chartSeries.primary,
    quota: palette.chartSeries.secondary,
    arrival: palette.chartSeries.tertiary,
    exchange: palette.chartSeries.quaternary,
  };
  const chartData = buildHourlySeries(data?.current ?? [], (slot) => ({
    slot,
    label: formatHourLabel(slot),
    collection: 0,
    quota: 0,
    arrival: 0,
    exchange: 0,
  })).map((row) => ({
    label: formatHourLabel(row.slot),
    collection: row.collection ?? 0,
    quota: row.quota ?? 0,
    arrival: row.arrival ?? 0,
    exchange: row.exchange ?? 0,
  }));

  return (
    <div className="imc-chart" style={{ height: 220, minWidth: 0, display: "flex", flexDirection: "column", marginTop: 12 }}>
      <HourlyChartUnitHeader left="하차차량(대)" />
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
              width={HOURLY_COUNT_Y_AXIS_WIDTH}
              tick={(props) => (
                <HourlyYAxisTick
                  {...props}
                  fill={palette.chartText}
                  orientation="left"
                  text={`${props.payload?.value ?? ""}대`}
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
                return [`${num.toLocaleString("ko-KR")}대`, name];
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
                  {SERIES.map((item) => (
                    <li key={item.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <span
                        style={{
                          display: "inline-block",
                          width: 12,
                          height: 12,
                          borderRadius: 2,
                          background: colors[item.key],
                        }}
                      />
                      {item.label}
                    </li>
                  ))}
                </ul>
              )}
            />
            <Bar dataKey="collection" name="수집" stackId="unload" fill={colors.collection} radius={[0, 0, 0, 0]} />
            <Bar dataKey="quota" name="쿼터" stackId="unload" fill={colors.quota} radius={[0, 0, 0, 0]} />
            <Bar dataKey="arrival" name="도착" stackId="unload" fill={colors.arrival} radius={[0, 0, 0, 0]} />
            <Bar dataKey="exchange" name="교환" stackId="unload" fill={colors.exchange} radius={[4, 4, 0, 0]} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
