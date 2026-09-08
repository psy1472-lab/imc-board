import { useEffect, useMemo, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { formatDateWithWeekday } from "../../lib/dateFormat";
import { resolveCalendarDayKind } from "../../lib/koreanHolidays";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"] as const;

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseIsoDate(dateStr: string): Date | null {
  const match = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function buildMonthGrid(year: number, month: number): Date[] {
  const firstDay = new Date(year, month, 1);
  const start = new Date(year, month, 1 - firstDay.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    return new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
  });
}

type ReportDateCalendarProps = {
  dates: string[];
  value: string;
  onChange: (date: string) => void;
};

export function ReportDateCalendar({ dates, value, onChange }: ReportDateCalendarProps) {
  const { palette } = useTheme();
  const availableDates = useMemo(() => new Set(dates), [dates]);
  const selectedDate = parseIsoDate(value);
  const [viewYear, setViewYear] = useState(() => selectedDate?.getFullYear() ?? new Date().getFullYear());
  const [viewMonth, setViewMonth] = useState(() => selectedDate?.getMonth() ?? new Date().getMonth());

  useEffect(() => {
    if (!selectedDate) return;
    setViewYear(selectedDate.getFullYear());
    setViewMonth(selectedDate.getMonth());
  }, [value]);

  const monthDays = buildMonthGrid(viewYear, viewMonth);
  const monthLabel = `${viewYear}년 ${viewMonth + 1}월`;

  const moveMonth = (offset: number) => {
    const next = new Date(viewYear, viewMonth + offset, 1);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
  };

  const jumpToLatest = () => {
    const latest = dates[dates.length - 1];
    if (!latest) return;
    onChange(latest);
    const parsed = parseIsoDate(latest);
    if (!parsed) return;
    setViewYear(parsed.getFullYear());
    setViewMonth(parsed.getMonth());
  };

  return (
    <div
      style={{
        background: palette.inputBg,
        border: `1px solid ${palette.border}`,
        borderRadius: 8,
        padding: 10,
        marginBottom: 12,
      }}
    >
      {value ? (
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, textAlign: "center" }}>
          현 보고서 : {formatDateWithWeekday(value)}
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
          gap: 6,
        }}
      >
        <button
          type="button"
          onClick={() => moveMonth(-1)}
          aria-label="이전 달"
          style={navButtonStyle(palette)}
        >
          ‹
        </button>
        <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap" }}>{monthLabel}</div>
        <button
          type="button"
          onClick={() => moveMonth(1)}
          aria-label="다음 달"
          style={navButtonStyle(palette)}
        >
          ›
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          gap: 2,
          marginBottom: 4,
        }}
      >
        {WEEKDAYS.map((weekday, index) => (
          <div
            key={weekday}
            style={{
              textAlign: "center",
              fontSize: 10,
              color: index === 0 ? palette.critical : index === 6 ? palette.caution : palette.muted,
              padding: "2px 0",
            }}
          >
            {weekday}
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2 }}>
        {monthDays.map((day) => {
          const iso = toIsoDate(day);
          const inMonth = day.getMonth() === viewMonth;
          const hasReport = availableDates.has(iso);
          const isSelected = value === iso;
          const dayKind = resolveCalendarDayKind(iso, day.getDay());
          const dayColor = getDayColor(dayKind, palette, inMonth, hasReport);

          return (
            <button
              key={iso}
              type="button"
              disabled={!hasReport}
              onClick={() => onChange(iso)}
              aria-label={formatDateWithWeekday(iso)}
              aria-pressed={isSelected}
              style={{
                border: isSelected ? `1px solid ${palette.caution}` : "1px solid transparent",
                borderRadius: 6,
                padding: "4px 0 5px",
                fontSize: 11,
                lineHeight: 1,
                cursor: hasReport ? "pointer" : "default",
                background: isSelected ? palette.panel : "transparent",
                color: dayColor,
                opacity: inMonth ? (hasReport ? 1 : 0.55) : 0,
                fontWeight: isSelected ? 700 : 400,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 3,
                minHeight: 32,
              }}
            >
              <span>{inMonth ? day.getDate() : ""}</span>
              {inMonth && hasReport ? (
                <span
                  aria-hidden="true"
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: palette.normal,
                    flexShrink: 0,
                  }}
                />
              ) : (
                <span aria-hidden="true" style={{ width: 5, height: 5, flexShrink: 0 }} />
              )}
            </button>
          );
        })}
      </div>

      {dates.length > 0 ? (
        <button
          type="button"
          onClick={jumpToLatest}
          style={{
            width: "100%",
            marginTop: 8,
            padding: "6px 8px",
            fontSize: 11,
            borderRadius: 6,
            border: `1px solid ${palette.border}`,
            background: palette.panelAlt,
            color: palette.muted,
            cursor: "pointer",
          }}
        >
          최신 보고서
        </button>
      ) : null}
    </div>
  );
}

function navButtonStyle(palette: { border: string; panelAlt: string; text: string }) {
  return {
    width: 28,
    height: 28,
    borderRadius: 6,
    border: `1px solid ${palette.border}`,
    background: palette.panelAlt,
    color: palette.text,
    cursor: "pointer",
    fontSize: 16,
    lineHeight: 1,
    padding: 0,
  };
}

function getDayColor(
  dayKind: ReturnType<typeof resolveCalendarDayKind>,
  palette: { critical: string; caution: string; text: string; muted: string },
  inMonth: boolean,
  hasReport: boolean,
) {
  if (!inMonth) return "transparent";
  if (dayKind === "holiday" || dayKind === "sunday") return palette.critical;
  if (dayKind === "saturday") return palette.caution;
  return hasReport ? palette.text : palette.muted;
}
