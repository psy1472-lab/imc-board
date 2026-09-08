import { useCallback, useEffect, useState } from "react";
import { PageState } from "../components/PageState";
import { useTheme } from "../context/ThemeContext";
import { fetchHealth, fetchSystemStatus, fetchThresholds, updateThreshold } from "../lib/api";
import { formatBytes } from "../lib/download";
import { formatDateWithWeekday } from "../lib/dateFormat";
import type { SystemStatus, ThresholdConfig } from "../types/system";

const METRIC_LABELS: Record<string, string> = {
  ips_rate: "IPS 판독률",
};

function StatusBadge({ label, tone }: { label: string; tone: "normal" | "warning" | "critical" }) {
  const { palette } = useTheme();
  const color =
    tone === "critical" ? palette.critical : tone === "warning" ? palette.warning : palette.normal;

  return (
    <span
      style={{
        display: "inline-block",
        padding: "4px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        color,
        border: `1px solid ${color}`,
        background: `${color}14`,
      }}
    >
      {label}
    </span>
  );
}

export default function SettingsPage() {
  const { palette } = useTheme();
  const [health, setHealth] = useState<string | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingMetric, setSavingMetric] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Partial<ThresholdConfig>>>({});

  const panelStyle = {
    background: palette.panel,
    border: `1px solid ${palette.border}`,
    borderRadius: 14,
    padding: 16,
  };

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthResult, statusResult, thresholdResult] = await Promise.all([
        fetchHealth(),
        fetchSystemStatus(),
        fetchThresholds(),
      ]);
      setHealth(healthResult.status);
      setStatus(statusResult);
      setThresholds(thresholdResult);
      const nextDrafts: Record<string, Partial<ThresholdConfig>> = {};
      thresholdResult.forEach((item) => {
        nextDrafts[item.metricName] = {
          warningMin: item.warningMin,
          criticalMin: item.criticalMin,
        };
      });
      setDrafts(nextDrafts);
    } catch {
      setError("시스템 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const handleSaveThreshold = async (metricName: string) => {
    const draft = drafts[metricName];
    if (!draft) return;
    setSavingMetric(metricName);
    setMessage(null);
    setError(null);
    try {
      await updateThreshold(metricName, {
        warningMin: draft.warningMin ?? null,
        criticalMin: draft.criticalMin ?? null,
      });
      setMessage(`${METRIC_LABELS[metricName] ?? metricName} 기준값을 저장했습니다.`);
      await loadAll();
    } catch {
      setError("기준값 저장에 실패했습니다.");
    } finally {
      setSavingMetric(null);
    }
  };

  if (loading && !status) {
    return <PageState loading />;
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={panelStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <div>
            <h2 style={{ margin: "0 0 8px", fontSize: 22 }}>시스템 관리</h2>
            <p style={{ margin: 0, color: palette.muted, fontSize: 14 }}>
              API 상태, DB 현황, KPI 기준값을 확인하고 관리합니다.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadAll()}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: `1px solid ${palette.border}`,
              background: palette.inputBg,
              color: palette.text,
              cursor: "pointer",
            }}
          >
            새로고침
          </button>
        </div>
      </div>

      {message ? (
        <div style={{ ...panelStyle, color: palette.normal, borderColor: palette.normal }}>{message}</div>
      ) : null}
      {error ? (
        <div style={{ ...panelStyle, color: palette.critical, borderColor: palette.critical }}>{error}</div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 16 }}>
        <div style={panelStyle}>
          <div style={{ color: palette.muted, fontSize: 12, marginBottom: 8 }}>API 상태</div>
          <StatusBadge
            label={health === "ok" ? "정상" : "확인 필요"}
            tone={health === "ok" ? "normal" : "warning"}
          />
        </div>
        <div style={panelStyle}>
          <div style={{ color: palette.muted, fontSize: 12, marginBottom: 8 }}>수집 보고서</div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{status?.reportCount ?? 0}건</div>
          <div style={{ color: palette.muted, fontSize: 12, marginTop: 6 }}>
            {status?.earliestDate && status?.latestDate
              ? `${formatDateWithWeekday(status.earliestDate)} ~ ${formatDateWithWeekday(status.latestDate)}`
              : "데이터 없음"}
          </div>
        </div>
        <div style={panelStyle}>
          <div style={{ color: palette.muted, fontSize: 12, marginBottom: 8 }}>검증 이슈</div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: (status?.validationIssues ?? 0) > 0 ? palette.warning : palette.text,
            }}
          >
            {status?.validationIssues ?? 0}건
          </div>
          <div style={{ color: palette.muted, fontSize: 12, marginTop: 6 }}>
            이상징후 {status?.anomalyCount ?? 0}건
          </div>
        </div>
      </div>

      <div style={panelStyle}>
        <h3 style={{ marginTop: 0 }}>데이터베이스</h3>
        <div style={{ display: "grid", gap: 8, fontSize: 14 }}>
          <div>
            <span style={{ color: palette.muted }}>경로: </span>
            <code>{status?.dbPath ?? "-"}</code>
          </div>
          <div>
            <span style={{ color: palette.muted }}>상태: </span>
            {status?.dbExists ? (
              <StatusBadge label="연결됨" tone="normal" />
            ) : (
              <StatusBadge label="파일 없음" tone="critical" />
            )}
          </div>
          <div>
            <span style={{ color: palette.muted }}>용량: </span>
            {formatBytes(status?.dbSizeBytes ?? 0)}
          </div>
          <div>
            <span style={{ color: palette.muted }}>기준값 설정: </span>
            {status?.thresholdCount ?? 0}개 지표
          </div>
        </div>
      </div>

      <div style={panelStyle}>
        <h3 style={{ marginTop: 0 }}>KPI 기준값</h3>
        <p style={{ marginTop: 0, color: palette.muted, fontSize: 13 }}>
          상태 판정에 사용되는 임계값입니다. AGENTS.md 원칙에 따라 DB에서 관리합니다.
        </p>
        {thresholds.length === 0 ? (
          <div style={{ color: palette.muted }}>등록된 기준값이 없습니다.</div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {thresholds.map((item) => {
              const draft = drafts[item.metricName] ?? {};
              return (
                <div
                  key={item.metricName}
                  style={{
                    border: `1px solid ${palette.border}`,
                    borderRadius: 10,
                    padding: 12,
                    display: "grid",
                    gap: 10,
                  }}
                >
                  <div style={{ fontWeight: 600 }}>
                    {METRIC_LABELS[item.metricName] ?? item.metricName}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 10 }}>
                    <label style={{ fontSize: 13 }}>
                      <div style={{ color: palette.muted, marginBottom: 4 }}>주의 하한</div>
                      <input
                        type="number"
                        step="0.1"
                        value={draft.warningMin ?? ""}
                        onChange={(event) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [item.metricName]: {
                              ...prev[item.metricName],
                              warningMin: event.target.value === "" ? null : Number(event.target.value),
                            },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: 8,
                          borderRadius: 8,
                          border: `1px solid ${palette.border}`,
                          background: palette.inputBg,
                          color: palette.text,
                        }}
                      />
                    </label>
                    <label style={{ fontSize: 13 }}>
                      <div style={{ color: palette.muted, marginBottom: 4 }}>위험 하한</div>
                      <input
                        type="number"
                        step="0.1"
                        value={draft.criticalMin ?? ""}
                        onChange={(event) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [item.metricName]: {
                              ...prev[item.metricName],
                              criticalMin: event.target.value === "" ? null : Number(event.target.value),
                            },
                          }))
                        }
                        style={{
                          width: "100%",
                          padding: 8,
                          borderRadius: 8,
                          border: `1px solid ${palette.border}`,
                          background: palette.inputBg,
                          color: palette.text,
                        }}
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => void handleSaveThreshold(item.metricName)}
                      disabled={savingMetric === item.metricName}
                      style={{
                        alignSelf: "end",
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: `1px solid ${palette.border}`,
                        background: palette.inputBg,
                        color: palette.text,
                        cursor: "pointer",
                      }}
                    >
                      {savingMetric === item.metricName ? "저장 중..." : "저장"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
