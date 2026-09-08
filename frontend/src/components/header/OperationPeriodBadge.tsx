import { useTheme } from "../../context/ThemeContext";
import { formatCompactPeriodRange, formatDateWithWeekday } from "../../lib/dateFormat";
import { OPERATION_PERIOD_STATUS } from "../../lib/operationPeriodMatch";
import { severityColor, type ThemePalette } from "../../styles/theme";
import { OPERATION_PERIOD_LABELS, type OperationPeriodType } from "../../types/operationPeriod";

type Props = {
  periodType: OperationPeriodType;
  startDate: string;
  endDate: string;
  note?: string | null;
};

function badgeBackground(status: string, palette: ThemePalette) {
  const color = severityColor(status, palette);
  return `${color}26`;
}

export function OperationPeriodBadge({ periodType, startDate, endDate, note }: Props) {
  const { palette } = useTheme();
  const status = OPERATION_PERIOD_STATUS[periodType];
  const color = severityColor(status, palette);
  const label = OPERATION_PERIOD_LABELS[periodType];
  const compactRange = formatCompactPeriodRange(startDate, endDate);
  const display = compactRange ? `${label}(${compactRange})` : label;
  const fullRange =
    startDate === endDate
      ? formatDateWithWeekday(startDate)
      : `${formatDateWithWeekday(startDate)} ~ ${formatDateWithWeekday(endDate)}`;
  const titleParts = [`${label} · ${fullRange}`];
  if (note && note !== label) {
    titleParts.push(note);
  }
  const title = titleParts.join(" · ");

  return (
    <div
      title={title}
      style={{
        background: badgeBackground(status, palette),
        color,
        border: `1px solid ${color}`,
        borderRadius: 999,
        padding: "2px 7px",
        fontWeight: 600,
        fontSize: 11,
        lineHeight: 1.3,
        whiteSpace: "nowrap",
        display: "inline-block",
        maxWidth: "100%",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {display}
    </div>
  );
}
