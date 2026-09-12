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
import { chartColors } from "../../lib/chartColors";
import { formatNumber } from "../../styles/theme";
import {
  buildEquipmentTrendChartData,
  getEquipmentTrendXAxisProps,
  EQUIPMENT_TREND_MARGIN_WITH_AXIS,
} from "../../lib/equipmentTrendChartData";

type Props = {
  data: EquipmentTrendSeries;
  referenceDate?: string;
};

export function EquipmentThroughputChart({ data, referenceDate }: Props) {
  const { palette } = useTheme();
  const colors = chartColors(palette);
  const isWeekdayMode = data.mode === "weekday";
  const chartData = buildEquipmentTrendChartData(data, referenceDate);

  return (
    <div style={{ height: 280, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={EQUIPMENT_TREND_MARGIN_WITH_AXIS}>
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            stroke={palette.chartText}
            {...getEquipmentTrendXAxisProps(chartData.length, isWeekdayMode, palette.chartText)}
          />
          <YAxis
            stroke={palette.chartText}
            width={56}
            tick={{ fill: palette.chartText, fontSize: 11 }}
            tickFormatter={(value) => formatNumber(value)}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            formatter={(value, name) => [formatNumber(value as number), String(name)]}
          />
          <Legend />
          <Bar
            dataKey="peakThroughput"
            name="시간당 피크"
            fill={colors.primary}
            radius={[4, 4, 0, 0]}
            maxBarSize={28}
          />
          <Line
            type="monotone"
            dataKey="avgThroughput"
            name="시간당 평균"
            stroke={colors.tertiary}
            strokeWidth={2}
            dot={{ r: 3, fill: colors.tertiary, strokeWidth: 0 }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
