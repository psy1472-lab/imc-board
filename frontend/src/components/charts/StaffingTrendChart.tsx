import {
  Bar,
  CartesianGrid,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { StaffingTrendSeries } from "../../types/staffingAnalysis";
import { useTheme } from "../../context/ThemeContext";
import { chartColors } from "../../lib/chartColors";
import {
  buildStaffingTrendChartData,
  getStaffingTrendXAxisProps,
  STAFFING_TREND_MARGIN,
  STAFFING_TREND_MARGIN_WITH_AXIS,
  STAFFING_TREND_SYNC_ID,
  STAFFING_TREND_Y_AXIS_WIDTH,
  type StaffingTrendChartPoint,
} from "../../lib/staffingTrendChartData";

type Props = {
  data: StaffingTrendSeries;
  referenceDate?: string;
  chartData?: StaffingTrendChartPoint[];
  hideXAxis?: boolean;
};

const LEGEND = (colors: ReturnType<typeof chartColors>) => [
  { key: "productivity", label: "인시당 처리량", color: colors.warning, shape: "line" as const },
  { key: "avgStaff", label: "평균 실근무", color: colors.tertiary, shape: "bar" as const },
] as const;

function formatProductivityLabel(value: unknown) {
  const num = typeof value === "number" ? value : Number(value);
  if (!num || Number.isNaN(num)) return "";
  return num.toFixed(1);
}

function formatStaffLabel(value: unknown) {
  const num = typeof value === "number" ? value : Number(value);
  if (!num || Number.isNaN(num)) return "";
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
}

type EdgeLabelProps = {
  x?: string | number;
  y?: string | number;
  value?: string | number;
  index?: number;
  fill: string;
  position: "top" | "bottom";
  pointCount: number;
  format: (value: unknown) => string;
};

function EdgeAwareValueLabel({ x = 0, y = 0, value, index = 0, fill, position, pointCount, format }: EdgeLabelProps) {
  const text = format(value);
  if (!text) return null;

  const isFirst = index === 0;
  const isLast = index === pointCount - 1;
  const dx = isFirst ? 10 : isLast ? -10 : 0;
  const dy = position === "top" ? -6 : 14;
  const textAnchor = isFirst ? "start" : isLast ? "end" : "middle";
  const xPos = typeof x === "number" ? x : Number(x);
  const yPos = typeof y === "number" ? y : Number(y);

  return (
    <text x={xPos + dx} y={yPos + dy} fill={fill} fontSize={10} textAnchor={textAnchor}>
      {text}
    </text>
  );
}

export function StaffingTrendChart({
  data,
  referenceDate,
  chartData: chartDataProp,
  hideXAxis = false,
}: Props) {
  const { palette } = useTheme();
  const colors = chartColors(palette);
  const legend = LEGEND(colors);
  const isWeekdayMode = data.mode === "weekday";
  const chartData = chartDataProp ?? buildStaffingTrendChartData(data, referenceDate);

  return (
    <div style={{ height: hideXAxis ? 280 : 320, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={chartData}
          syncId={STAFFING_TREND_SYNC_ID}
          margin={hideXAxis ? STAFFING_TREND_MARGIN : STAFFING_TREND_MARGIN_WITH_AXIS}
          barCategoryGap="18%"
        >
          <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
          <XAxis
            stroke={palette.chartText}
            {...getStaffingTrendXAxisProps(chartData.length, isWeekdayMode, hideXAxis, palette.chartText)}
          />
          <YAxis
            yAxisId="productivity"
            stroke={palette.chartText}
            width={STAFFING_TREND_Y_AXIS_WIDTH}
            tick={{ fill: palette.chartText, fontSize: 11 }}
            tickFormatter={(value) => `${value}`}
          />
          <YAxis
            yAxisId="staff"
            orientation="right"
            stroke={palette.chartText}
            width={48}
            allowDecimals={false}
            tick={{ fill: palette.chartText, fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              color: palette.text,
            }}
            labelFormatter={(_, payload) => {
              const item = payload?.[0]?.payload as StaffingTrendChartPoint | undefined;
              if (!item) return "";
              return isWeekdayMode ? `${item.dateText}요일 평균 ${item.weekdayText}` : item.axisLabel;
            }}
            formatter={(value, name) => {
              if (name === "평균 실근무") return [`${value ?? "-"}명`, String(name)];
              return [`${Number(value ?? 0).toFixed(1)}개`, String(name)];
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
                        height: item.shape === "bar" ? 12 : 3,
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
            yAxisId="staff"
            dataKey="avgStaff"
            name="평균 실근무"
            fill={colors.tertiary}
            radius={[4, 4, 0, 0]}
            maxBarSize={isWeekdayMode ? 36 : 24}
          >
            <LabelList
              dataKey="avgStaff"
              content={(props) => (
                <EdgeAwareValueLabel
                  x={props.x}
                  y={props.y}
                  value={
                    typeof props.value === "string" || typeof props.value === "number"
                      ? props.value
                      : undefined
                  }
                  index={props.index}
                  fill={colors.tertiary}
                  position="top"
                  pointCount={chartData.length}
                  format={formatStaffLabel}
                />
              )}
            />
          </Bar>
          <Line
            yAxisId="productivity"
            type="monotone"
            dataKey="productivity"
            name="인시당 처리량"
            stroke={colors.warning}
            strokeWidth={2}
            dot={{ r: 3, fill: colors.warning, strokeWidth: 0 }}
            connectNulls
          >
            <LabelList
              dataKey="productivity"
              content={(props) => (
                <EdgeAwareValueLabel
                  x={props.x}
                  y={props.y}
                  value={
                    typeof props.value === "string" || typeof props.value === "number"
                      ? props.value
                      : undefined
                  }
                  index={props.index}
                  fill={colors.warning}
                  position="top"
                  pointCount={chartData.length}
                  format={formatProductivityLabel}
                />
              )}
            />
          </Line>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
