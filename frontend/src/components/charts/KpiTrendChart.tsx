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

type Props = {
  data: DashboardSummary["trend7d"];
};

const TREND_LEGEND = (colors: ReturnType<typeof chartColors>) => [
  { key: "totalVolume", label: "처리물량(천)", color: colors.primary },
  { key: "ipsRate", label: "IPS(%)", color: colors.tertiary },
  { key: "rejectRate", label: "Reject(%)", color: colors.critical },
] as const;

export function KpiTrendChart({ data }: Props) {
  const { palette } = useTheme();
  const colors = chartColors(palette);
  const legend = TREND_LEGEND(colors);
  const chartData = data.dates.map((date, index) => ({
    date,
    totalVolume: (data.totalVolume[index] ?? 0) / 1000,
    ipsRate: data.ipsRate[index] ?? null,
    rejectRate: data.rejectRate[index] ?? null,
  }));

  return (
    <div style={{ height: 240, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis dataKey="date" stroke={palette.chartText} />
          <YAxis
            yAxisId="volume"
            stroke={palette.chartText}
            domain={[0, "auto"]}
            allowDecimals={false}
            tickFormatter={(value) => `${value}`}
          />
          <YAxis
            yAxisId="rate"
            orientation="right"
            stroke={palette.chartText}
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            formatter={(value, name) => {
              const num = typeof value === "number" ? value : Number(value);
              if (name === "처리물량(천)") return [`${num.toLocaleString()}천`, name];
              return [`${num}%`, name];
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
                {legend.map((item) => (
                  <li key={item.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        display: "inline-block",
                        width: 12,
                        height: item.key === "totalVolume" ? 12 : 3,
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
            name="처리물량(천)"
            fill={colors.primary}
            radius={[4, 4, 0, 0]}
            maxBarSize={32}
          />
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="ipsRate"
            name="IPS(%)"
            stroke={colors.tertiary}
            dot={false}
            connectNulls
          />
          <Line
            yAxisId="rate"
            type="monotone"
            dataKey="rejectRate"
            name="Reject(%)"
            stroke={colors.critical}
            dot={false}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
