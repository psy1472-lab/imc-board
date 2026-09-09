import { useCallback, useEffect, useMemo, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import {
  createOperationPeriod,
  deleteOperationPeriod,
  fetchOperationPeriods,
  updateOperationPeriod,
} from "../../lib/api";
import { formatDateWithWeekday } from "../../lib/dateFormat";
import {
  OPERATION_PERIOD_DESCRIPTIONS,
  OPERATION_PERIOD_LABELS,
  type OperationPeriod,
  type OperationPeriodType,
} from "../../types/operationPeriod";

const PERIOD_TYPES: OperationPeriodType[] = [
  "post_shopping_discount",
  "special_communication",
  "no_parcel_day",
];

function formatPeriodRange(startDate: string, endDate: string) {
  if (startDate === endDate) {
    return formatDateWithWeekday(startDate);
  }
  return `${formatDateWithWeekday(startDate)} ~ ${formatDateWithWeekday(endDate)}`;
}

function inputStyle(
  palette: ReturnType<typeof useTheme>["palette"],
  invalid = false,
) {
  return {
    padding: "8px 10px",
    background: palette.inputBg,
    color: palette.text,
    border: `1px solid ${invalid ? palette.critical : palette.border}`,
    borderRadius: 8,
    fontSize: 13,
    minWidth: 0,
  };
}

export function OperationPeriodPanel() {
  const { palette } = useTheme();
  const [periods, setPeriods] = useState<OperationPeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingAction, setSavingAction] = useState<"add" | "update" | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [periodType, setPeriodType] = useState<OperationPeriodType>("special_communication");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [note, setNote] = useState("");

  const panelStyle = {
    background: palette.panel,
    border: `1px solid ${palette.border}`,
    borderRadius: 14,
    padding: 16,
  };

  const dateRangeInvalid = Boolean(startDate && endDate && endDate < startDate);

  const groupedPeriods = useMemo(() => {
    const groups: Record<OperationPeriodType, OperationPeriod[]> = {
      post_shopping_discount: [],
      special_communication: [],
      no_parcel_day: [],
    };
    periods.forEach((period) => {
      groups[period.periodType].push(period);
    });
    return groups;
  }, [periods]);

  const loadPeriods = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchOperationPeriods();
      setPeriods(items);
    } catch {
      setError("운영 특이 일정을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPeriods();
  }, [loadPeriods]);

  const resetForm = () => {
    setEditingId(null);
    setStartDate("");
    setEndDate("");
    setNote("");
  };

  const buildPayload = () => {
    if (!startDate) {
      return null;
    }
    const resolvedEndDate = endDate || startDate;
    if (resolvedEndDate < startDate) {
      return null;
    }
    return {
      periodType,
      startDate,
      endDate: resolvedEndDate,
      note: note.trim() || undefined,
    };
  };

  const handleSelectPeriod = (period: OperationPeriod) => {
    setEditingId(period.id);
    setPeriodType(period.periodType);
    setStartDate(period.startDate);
    setEndDate(period.endDate);
    setNote(period.note ?? "");
    setError(null);
    setMessage(null);
  };

  const handleAdd = async () => {
    const payload = buildPayload();
    if (!payload) {
      setError("시작일을 입력해 주세요.");
      return;
    }

    setSaving(true);
    setSavingAction("add");
    setError(null);
    setMessage(null);
    try {
      const created = await createOperationPeriod(payload);
      setPeriods((current) => [created, ...current]);
      setMessage(`${OPERATION_PERIOD_LABELS[payload.periodType]} 일정을 추가했습니다.`);
      resetForm();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "추가에 실패했습니다.");
    } finally {
      setSaving(false);
      setSavingAction(null);
    }
  };

  const handleUpdate = async () => {
    if (!editingId) {
      setError("수정할 일정을 목록에서 선택해 주세요.");
      return;
    }
    const payload = buildPayload();
    if (!payload) {
      setError("시작일을 입력해 주세요.");
      return;
    }

    setSaving(true);
    setSavingAction("update");
    setError(null);
    setMessage(null);
    try {
      const updated = await updateOperationPeriod(editingId, payload);
      setPeriods((current) =>
        current.map((period) => (period.id === editingId ? updated : period)),
      );
      setMessage(`${OPERATION_PERIOD_LABELS[payload.periodType]} 일정을 수정했습니다.`);
      resetForm();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "수정에 실패했습니다.");
    } finally {
      setSaving(false);
      setSavingAction(null);
    }
  };

  const handleDeleteSelected = async () => {
    if (!editingId) {
      setError("삭제할 일정을 목록에서 선택해 주세요.");
      return;
    }

    setDeletingId(editingId);
    setError(null);
    setMessage(null);
    try {
      await deleteOperationPeriod(editingId);
      setPeriods((current) => current.filter((period) => period.id !== editingId));
      setMessage("일정을 삭제했습니다.");
      resetForm();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "삭제에 실패했습니다.");
    } finally {
      setDeletingId(null);
    }
  };

  const formInvalid = !startDate || dateRangeInvalid;
  const isBusy = saving || deletingId !== null;

  const actionButtonStyle = (
    variant: "add" | "edit" | "delete",
    disabled: boolean,
  ) => {
    const backgrounds = {
      add: palette.caution,
      edit: palette.normal,
      delete: palette.inputBg,
    };
    const colors = {
      add: palette.text,
      edit: palette.text,
      delete: palette.critical,
    };
    return {
      padding: "9px 14px",
      borderRadius: 8,
      border: variant === "delete" ? `1px solid ${palette.critical}` : "none",
      background: disabled ? palette.border : backgrounds[variant],
      color: disabled ? palette.muted : colors[variant],
      fontSize: 13,
      fontWeight: 600,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.7 : 1,
      whiteSpace: "nowrap" as const,
    };
  };

  return (
    <div style={panelStyle}>
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 6px", fontSize: 18 }}>운영 특이 일정</h3>
        <p style={{ margin: 0, color: palette.muted, fontSize: 13, lineHeight: 1.6 }}>
          우체국쇼핑대전, 특별소통기간, 위탁배달원 하계 휴식기간 등 물량·소통 분석 시 참고할 일정을 등록합니다.
        </p>
      </div>

      {message ? (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            borderRadius: 10,
            border: `1px solid ${palette.normal}`,
            color: palette.normal,
            fontSize: 13,
          }}
        >
          {message}
        </div>
      ) : null}
      {error ? (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            borderRadius: 10,
            border: `1px solid ${palette.critical}`,
            color: palette.critical,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gap: 12,
          padding: 14,
          borderRadius: 12,
          background: palette.panelAlt,
          border: `1px solid ${palette.border}`,
          marginBottom: 16,
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 12,
            alignItems: "end",
          }}
        >
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: palette.muted }}>유형</span>
            <select
              value={periodType}
              onChange={(event) => setPeriodType(event.target.value as OperationPeriodType)}
              style={inputStyle(palette)}
            >
              {PERIOD_TYPES.map((type) => (
                <option key={type} value={type}>
                  {OPERATION_PERIOD_LABELS[type]}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: palette.muted }}>시작일</span>
            <input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
              style={inputStyle(palette)}
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: palette.muted }}>종료일</span>
            <input
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
              style={inputStyle(palette, dateRangeInvalid)}
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 13, color: palette.muted }}>메모</span>
            <input
              type="text"
              value={note}
              placeholder="선택 입력"
              onChange={(event) => setNote(event.target.value)}
              style={inputStyle(palette)}
            />
          </label>

          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <button
              type="button"
              onClick={() => void handleAdd()}
              disabled={isBusy || formInvalid}
              style={actionButtonStyle("add", isBusy || formInvalid)}
            >
              {savingAction === "add" ? "추가 중..." : "추가"}
            </button>
            <button
              type="button"
              onClick={() => void handleUpdate()}
              disabled={isBusy || formInvalid || editingId === null}
              style={actionButtonStyle("edit", isBusy || formInvalid || editingId === null)}
            >
              {savingAction === "update" ? "수정 중..." : "수정"}
            </button>
            <button
              type="button"
              onClick={() => void handleDeleteSelected()}
              disabled={isBusy || editingId === null}
              style={actionButtonStyle("delete", isBusy || editingId === null)}
            >
              {deletingId !== null ? "삭제 중..." : "삭제"}
            </button>
          </div>
        </div>

        <div style={{ fontSize: 12, color: palette.muted, lineHeight: 1.6 }}>
          {editingId
            ? "목록에서 선택한 일정을 수정하거나 삭제할 수 있습니다. 추가는 새 일정을 등록합니다."
            : null}
          {editingId ? " · " : null}
          {OPERATION_PERIOD_DESCRIPTIONS[periodType]}
          {" · 종료일을 비우면 시작일과 동일하게 저장됩니다."}
        </div>
      </div>

      {loading ? (
        <div style={{ color: palette.muted, fontSize: 13 }}>일정을 불러오는 중...</div>
      ) : periods.length === 0 ? (
        <div style={{ color: palette.muted, fontSize: 13 }}>등록된 운영 특이 일정이 없습니다.</div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {PERIOD_TYPES.map((type) => {
            const items = groupedPeriods[type];
            if (items.length === 0) return null;
            return (
              <div
                key={type}
                style={{
                  border: `1px solid ${palette.border}`,
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "10px 14px",
                    background: palette.panelAlt,
                    borderBottom: `1px solid ${palette.border}`,
                    fontSize: 13,
                    fontWeight: 600,
                  }}
                >
                  {OPERATION_PERIOD_LABELS[type]}
                  <span style={{ marginLeft: 8, color: palette.muted, fontWeight: 400 }}>
                    {items.length}건
                  </span>
                </div>
                <div style={{ display: "grid" }}>
                  {items.map((period) => {
                    const isSelected = editingId === period.id;
                    return (
                    <div
                      key={period.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSelectPeriod(period)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleSelectPeriod(period);
                        }
                      }}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                        padding: "12px 14px",
                        borderTop: `1px solid ${palette.border}`,
                        flexWrap: "wrap",
                        cursor: "pointer",
                        background: isSelected ? palette.panelAlt : "transparent",
                        outline: isSelected ? `2px solid ${palette.caution}` : "none",
                        outlineOffset: -2,
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>
                          {formatPeriodRange(period.startDate, period.endDate)}
                        </div>
                        {period.note ? (
                          <div style={{ marginTop: 4, fontSize: 12, color: palette.muted }}>
                            {period.note}
                          </div>
                        ) : null}
                      </div>
                      {isSelected ? (
                        <span style={{ fontSize: 12, color: palette.caution, whiteSpace: "nowrap" }}>
                          선택됨
                        </span>
                      ) : null}
                    </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
