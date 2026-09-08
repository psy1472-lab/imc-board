import { useTheme } from "../../context/ThemeContext";

type Props = {
  left?: string;
  right?: string;
};

export function HourlyChartUnitHeader({ left, right }: Props) {
  const { palette } = useTheme();

  if (!left && !right) return null;

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 12,
        fontSize: 10,
        color: palette.muted,
        padding: "0 4px 6px",
        minHeight: 14,
        whiteSpace: "nowrap",
      }}
    >
      <span>{left ?? ""}</span>
      <span>{right ?? ""}</span>
    </div>
  );
}
