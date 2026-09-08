import type { ReactNode } from "react";
import { useTheme } from "../context/ThemeContext";
import { panelStyle } from "../styles/panel";

type PageStateProps = {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
  children?: ReactNode;
};

export function PageState({
  loading,
  error,
  empty,
  emptyTitle = "보고서가 없습니다",
  emptyDescription = "선택한 날짜에 등록된 일일소통현황 PDF가 없습니다. 관리자 메뉴에서 PDF를 업로드해 주세요.",
  onRetry,
  children,
}: PageStateProps) {
  const { palette } = useTheme();

  if (loading) {
    return (
      <div
        style={{
          ...panelStyle(palette),
          color: palette.muted,
          fontSize: 14,
          textAlign: "center",
          padding: "32px 24px",
        }}
        role="status"
        aria-live="polite"
      >
        데이터를 불러오는 중...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          ...panelStyle(palette),
          borderColor: palette.critical,
          padding: "24px",
          textAlign: "center",
        }}
        role="alert"
      >
        <div style={{ color: palette.critical, marginBottom: 12, fontSize: 14 }}>{error}</div>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: `1px solid ${palette.border}`,
              background: palette.panelAlt,
              color: palette.text,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            다시 시도
          </button>
        ) : null}
      </div>
    );
  }

  if (empty) {
    return (
      <div
        style={{
          ...panelStyle(palette),
          padding: "32px 24px",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{emptyTitle}</div>
        <div style={{ color: palette.muted, fontSize: 13, lineHeight: 1.6, maxWidth: 480, margin: "0 auto" }}>
          {emptyDescription}
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
