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
import type {
  MachineSortingStream,
  MachineSortingStreamTrend,
  MachineSortingTrendSeries,
} from "../../types/equipmentAnalysis";
import { useTheme } from "../../context/ThemeContext";
import { chartColors } from "../../lib/chartColors";
import { formatNumber } from "../../styles/theme";
import { resolveTrendDate, splitShortDateWithWeekday } from "../../lib/dateFormat";
import {
  getEquipmentTrendXAxisProps,
  EQUIPMENT_TREND_MARGIN_WITH_AXIS,
} from "../../lib/equipmentTrendChartData";
import { HourlyChartUnitHeader } from "./HourlyChartUnitHeader";
import { HourlyYAxisTick } from "./HourlyYAxisTick";

type Props = {
  data: MachineSortingTrendSeries;
  stream: MachineSortingStream;
  referenceDate?: string;
  height?: number;
};

type ChartPoint = {
  axisLabel: string;
  dateText: string;
  weekdayText: string;
  deck1Volume: number | null;
  deck2Volume: number | null;
  deck3Volume: number | null;
  deck1Share: number | null;
  deck2Share: number | null;
  deck3Share: number | null;
};

const DECKS = [
  { volumeKey: "deck1Volume", shareKey: "deck1Share", label: "1단", colorKey: "primary" },
  { volumeKey: "deck2Volume", shareKey: "deck2Share", label: "2단", colorKey: "secondary" },
  { volumeKey: "deck3Volume", shareKey: "deck3Share", label: "3단", colorKey: "tertiary" },
] as const;

function formatShare(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return `${Number(value).toFixed(1)}%`;
}

function seriesAt(stream: MachineSortingStreamTrend, key: keyof MachineSortingStreamTrend, index: number) {
  return stream[key][index] ?? null;
}

function buildChartData(
  data: MachineSortingTrendSeries,
  stream: MachineSortingStream,
  referenceDate?: string,
): ChartPoint[] {
  const isWeekdayMode = data.mode === "weekday";
  const streamData = data[stream];
  return data.dates.map((shortDate, index) => {
    const values = {
      deck1Volume: seriesAt(streamData, "deck1Volume", index),
      deck2Volume: seriesAt(streamData, "deck2Volume", index),
      deck3Volume: seriesAt(streamData, "deck3Volume", index),
      deck1Share: seriesAt(streamData, "deck1Share", index),
      deck2Share: seriesAt(streamData, "deck2Share", index),
      deck3Share: seriesAt(streamData, "deck3Share", index),
    };
    if (isWeekdayMode) {
      const label = data.labels?.[index] ?? shortDate;
      const countText = data.sampleCounts?.[index] ? `(${data.sampleCounts[index]}일)` : "";
      return {
        axisLabel: `${label}${countText}`,
        dateText: label,
        weekdayText: countText,
        ...values,
      };
    }
    const fullDate = resolveTrendDate(data.reportDates?.[index], shortDate, referenceDate);
    const { dateText, weekdayText } = splitShortDateWithWeekday(fullDate);
    return {
      axisLabel: `${dateText}${weekdayText}`,
      dateText,
      weekdayText,
      ...values,
    };
  });
}

export function MachineSortingChart({ data, stream, referenceDate, height = 320 }: Props) {
  const { palette } = useTheme();
  const colors = chartColors(palette);
  const streamData = data?.[stream];
  const isWeekdayMode = data?.mode === "weekday";
  const chartData = data && streamData ? buildChartData(data, stream, referenceDate) : [];
  const hasValue = chartData.some((item) =>
    DECKS.some(
      (deck) => item[deck.volumeKey] != null || item[deck.shareKey] != null,
    ),
  );

  if (!hasValue) {
    return (
      <div style={{ color: palette.muted, fontSize: 13, padding: "28px 0" }}>
        기계구분 단별 추세 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div className="imc-chart" style={{ height, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <HourlyChartUnitHeader left="물량(개)" right="점유비(%)" />
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={EQUIPMENT_TREND_MARGIN_WITH_AXIS} barCategoryGap="18%" barGap={2}>
            <CartesianGrid stroke={palette.chartGrid} strokeDasharray="3 3" />
            <XAxis
              stroke={palette.chartText}
              {...getEquipmentTrendXAxisProps(chartData.length, isWeekdayMode, palette.chartText)}
            />
            <YAxis
              yAxisId="left"
              stroke={palette.chartText}
              domain={[0, "auto"]}
              allowDecimals={false}
              width={64}
              tick={(props) => (
                <HourlyYAxisTick
                  {...props}
                  fill={palette.chartText}
                  orientation="left"
                  text={formatNumber(props.payload?.value)}
                />
              )}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke={palette.chartText}
              domain={[0, (dataMax: number) => Math.max(50, Math.ceil((dataMax || 0) / 10) * 10)]}
              width={44}
              tick={(props) => (
                <HourlyYAxisTick
                  {...props}
                  fill={palette.chartText}
                  orientation="right"
                  text={`${props.payload?.value ?? ""}%`}
                />
              )}
            />
            <Tooltip
              contentStyle={{
                background: palette.panel,
                border: `1px solid ${palette.border}`,
                color: palette.text,
              }}
              labelFormatter={(_, payload) => {
                const item = payload?.[0]?.payload as ChartPoint | undefined;
                if (!item) return "";
                return isWeekdayMode ? `${item.dateText}요일 평균 ${item.weekdayText}` : item.axisLabel;
              }}
              formatter={(value, name) => {
                if (String(name).includes("점유비")) return [formatShare(value as number), String(name)];
                return [formatNumber(value as number), String(name)];
              }}
            />
            <Legend />
            {DECKS.map((deck) => (
              <Bar
                key={deck.volumeKey}
                yAxisId="left"
                dataKey={deck.volumeKey}
                name={`${deck.label} 물량`}
                fill={colors[deck.colorKey]}
                radius={[4, 4, 0, 0]}
                maxBarSize={isWeekdayMode ? 28 : 22}
              />
            ))}
            {DECKS.map((deck) => (
              <Line
                key={deck.shareKey}
                yAxisId="right"
                type="monotone"
                dataKey={deck.shareKey}
                name={`${deck.label} 점유비`}
                stroke={colors[deck.colorKey]}
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={{ r: 3 }}
                connectNulls
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
