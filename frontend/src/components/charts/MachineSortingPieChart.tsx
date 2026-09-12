import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { MachineSorting, MachineSortingDeck } from "../../types/equipmentAnalysis";
import { useTheme } from "../../context/ThemeContext";
import { chartColors } from "../../lib/chartColors";
import { formatNumber } from "../../styles/theme";

type Props = {
  data?: MachineSorting;
};

const DECKS = [
  { deck: 1, label: "1단", colorKey: "primary" },
  { deck: 2, label: "2단", colorKey: "secondary" },
  { deck: 3, label: "3단", colorKey: "tertiary" },
] as const;

type Slice = {
  label: string;
  volume: number | null;
  shareRate: number | null;
  value: number;
  color: string;
};

function formatShare(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return `${Number(value).toFixed(1)}%`;
}

function toSlices(
  rows: MachineSortingDeck[] | undefined,
  colors: ReturnType<typeof chartColors>,
): Slice[] {
  return DECKS.map((deck) => {
    const row = rows?.find((item) => item.deck === deck.deck);
    const volume = row?.volume ?? null;
    const shareRate = row?.shareRate ?? null;
    return {
      label: deck.label,
      volume,
      shareRate,
      value: volume && volume > 0 ? volume : shareRate && shareRate > 0 ? shareRate : 0,
      color: colors[deck.colorKey],
    };
  });
}

function StreamPie({ title, slices }: { title: string; slices: Slice[] }) {
  const { palette } = useTheme();
  const hasValue = slices.some((item) => item.value > 0);
  const total = slices.reduce((sum, item) => sum + (item.volume ?? 0), 0);

  return (
    <div style={{ minWidth: 0, overflow: "hidden" }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, textAlign: "center" }}>{title}</div>
      {hasValue ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, minWidth: 0 }}>
          <div style={{ width: 132, height: 132, flex: "0 0 132px", position: "relative" }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="label"
                  cx="50%"
                  cy="50%"
                  innerRadius={38}
                  outerRadius={58}
                  stroke={palette.panel}
                  strokeWidth={2}
                  paddingAngle={1.5}
                >
                  {slices.map((item) => (
                    <Cell key={item.label} fill={item.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: palette.panel,
                    border: `1px solid ${palette.border}`,
                    color: palette.text,
                  }}
                  formatter={(_, name, item) => {
                    const slice = item?.payload as Slice | undefined;
                    if (!slice) return ["-", String(name)];
                    return [`${formatNumber(slice.volume)} · ${formatShare(slice.shareRate)}`, slice.label];
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                pointerEvents: "none",
              }}
            >
              <div style={{ fontSize: 10, color: palette.muted }}>합계</div>
              <div style={{ fontSize: 12, fontWeight: 700 }}>{formatNumber(total)}</div>
            </div>
          </div>
          <div style={{ display: "grid", gap: 6, width: "100%", minWidth: 0 }}>
            {slices.map((item) => (
              <div
                key={item.label}
                style={{
                  display: "grid",
                  gridTemplateColumns: "8px 28px minmax(0, 1fr) auto",
                  alignItems: "baseline",
                  columnGap: 8,
                  fontSize: 12,
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 99,
                    background: item.color,
                    transform: "translateY(-1px)",
                  }}
                />
                <span style={{ color: palette.muted }}>{item.label}</span>
                <span
                  style={{
                    fontWeight: 600,
                    fontVariantNumeric: "tabular-nums",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {formatNumber(item.volume)}
                </span>
                <span style={{ color: palette.muted, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                  {formatShare(item.shareRate)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ color: palette.muted, fontSize: 13, padding: "24px 0", textAlign: "center" }}>
          해당일 기계구분 데이터가 없습니다.
        </div>
      )}
    </div>
  );
}

export function MachineSortingPieChart({ data }: Props) {
  const { palette } = useTheme();
  const colors = chartColors(palette);
  const dispatch = toSlices(data?.dispatch, colors);
  const arrival = toSlices(data?.arrival, colors);
  const hasValue = [...dispatch, ...arrival].some((item) => item.value > 0);

  if (!hasValue) {
    return (
      <div style={{ color: palette.muted, fontSize: 13, padding: "28px 0" }}>
        해당일 기계구분 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: 20,
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      <StreamPie title="발송" slices={dispatch} />
      <StreamPie title="도착" slices={arrival} />
    </div>
  );
}
