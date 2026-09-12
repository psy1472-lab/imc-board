import { Link } from "react-router-dom";
import { Panel } from "../components/layout/Panel";
import { useTheme } from "../context/ThemeContext";
import { panelAltStyle } from "../styles/panel";

const SCREENS = [
  {
    path: "/",
    title: "종합상황판",
    purpose: "당일 운영을 한 화면에서 빠르게 판단합니다.",
    look: "전국접수·총처리·발송·도착·잔량·인시당 처리량·IPS·최종 작업종료와 시간대별 처리량, 인력·운송·설비·안전 요약을 봅니다.",
  },
  {
    path: "/volume",
    title: "물량·소통 분석",
    purpose: "일·월·연 물량 추세와 전국 대비 처리율을 봅니다.",
    look: "전국접수, 총처리/발송/도착, 잔량, 전국대비처리율. 벤치마크 표를 클릭하면 비교 기준이 바뀝니다.",
  },
  {
    path: "/staffing",
    title: "인력·생산성 분석",
    purpose: "시간대별 인력과 생산성이 물량에 맞는지 확인합니다.",
    look: "인시당 처리량, 평균·피크 실근무, 피크 시간대와 그 시간 물량.",
  },
  {
    path: "/transport",
    title: "운송 관제",
    purpose: "쿼터·교환 준수와 집중국 초과·지연을 봅니다.",
    look: "쿼터/교환 준수율, 교환 잔량, 쿼터 초과·23시 초과 지연 집중국, 집중국별 표.",
  },
  {
    path: "/equipment",
    title: "설비·구분기 분석",
    purpose: "구분기 품질과 처리량 추세를 봅니다.",
    look: "IPS(목표 대비), 구분율, Reject율, 숏컷율, 시간당 평균/피크, 미판독, 기계구분 1·2·3단.",
  },
  {
    path: "/safety",
    title: "안전·이상징후",
    purpose: "안전점검, 재해, 운영 이상징후를 한곳에서 봅니다.",
    look: "점검 양호율, 재해 건수, 주의·위험 이상징후. 이상징후 카드를 클릭하면 상세가 열립니다.",
  },
  {
    path: "/briefing",
    title: "AI 운영 브리핑",
    purpose: "규칙 기반 일일 요약과 내일 전망을 참고합니다. 최종 판단은 담당자입니다.",
    look: "총처리·발송·도착·잔량, 인력·운송·설비·안전 평가, 특이사항, 예상 물량. 비교는 전일 기준입니다.",
  },
  {
    path: "/reports",
    title: "보고서·다운로드",
    purpose: "PDF 업로드, 검증, 다운로드. 관리자 전용입니다.",
    look: "운영기간 등록, PDF 수집, 검증(발송+도착=총처리 등), 보고서 목록.",
  },
  {
    path: "/settings",
    title: "시스템 관리",
    purpose: "시스템 상태와 KPI 임계값을 관리합니다. 관리자 전용입니다.",
    look: "API·DB 상태, IPS 판독률 주의/위험 하한.",
  },
];

const METRICS = [
  { name: "전국접수물량", meaning: "당일 전국에서 접수한 소포 물량입니다.", where: "종합상황판, 물량·소통" },
  { name: "총 처리물량", meaning: "중부권 IMC가 처리한 발송+도착 물량입니다.", where: "종합상황판, 물량·소통" },
  { name: "발송물량", meaning: "권역국내 수집물량과 (타집중국→센터 발송된) 쿼터물량입니다.", where: "종합상황판, 물량·소통" },
  { name: "도착물량", meaning: "센터에서 구분작업 이후 권역국으로 내보낸 물량입니다. 축약형 보고서는 배분물량으로 표시됩니다.", where: "종합상황판, 물량·소통" },
  { name: "잔량", meaning: "당일 처리하지 못한 물량입니다. 0이면 정상 소통입니다.", where: "종합상황판, 물량·소통" },
  { name: "전국대비처리율", meaning: "전국접수 대비 중부권 IMC 처리 비율입니다.", where: "물량·소통, 브리핑" },
  { name: "인시당 처리량", meaning: "실근무 1명이 1시간에 처리한 개수입니다.", where: "종합상황판, 인력·생산성" },
  { name: "실근무인력", meaning: "해당 시간대에 실제 투입된 인원입니다.", where: "인력·생산성" },
  { name: "쿼터 준수율", meaning: "집중국 쿼터 기준 대비 실제 운송 차량 비율입니다.", where: "운송 관제" },
  { name: "교환 준수율", meaning: "교환편 기준 대비 실제 차량 비율입니다.", where: "운송 관제" },
  { name: "교환 잔량", meaning: "교환편으로 나가지 못한 잔여 물량입니다.", where: "종합상황판, 운송 관제" },
  { name: "지연(23시 초과)", meaning: "최종 도착이 23시를 넘긴 집중국입니다.", where: "운송 관제" },
  { name: "IPS", meaning: "구분기가 주소를 판독한 비율(%)입니다. 목표 대비로 색이 바뀝니다.", where: "종합상황판, 설비·구분기" },
  { name: "구분율", meaning: "공급 물량 중 정상 구분된 비율입니다.", where: "설비·구분기" },
  { name: "Reject율", meaning: "구분 실패 비율입니다. 높으면 설비·품질을 점검합니다.", where: "설비·구분기" },
  { name: "숏컷율", meaning: "숏컷으로 빠진 물량 비율입니다.", where: "설비·구분기" },
  { name: "미판독", meaning: "주소 판독에 실패한 건수·비율입니다.", where: "설비·구분기" },
  { name: "기계구분 1·2·3단", meaning: "발송/도착 기계구분 단별 처리량과 점유비입니다.", where: "종합상황판, 설비·구분기" },
  { name: "안전점검 양호율", meaning: "점검 항목 중 양호 비율입니다.", where: "안전·이상징후" },
  { name: "재해 건수", meaning: "당일 보고된 재해 건수입니다. 경위는 이름 마스킹 후 표시됩니다.", where: "안전·이상징후" },
];

export default function UserGuidePage() {
  const { palette } = useTheme();

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 960 }}>
      <Panel title="사용자 가이드">
        <p style={{ margin: 0, color: palette.muted, lineHeight: 1.6 }}>
          중부권IMC 통합관제 대시보드의 목적, 화면, 주요 지표를 안내합니다.
        </p>
        <nav style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
          {[
            ["#purpose", "목적"],
            ["#howto", "화면 보는 법"],
            ["#screens", "주요 화면"],
            ["#metrics", "주요 지표"],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              style={{
                padding: "6px 10px",
                borderRadius: 999,
                border: `1px solid ${palette.border}`,
                background: palette.panelAlt,
                color: palette.text,
                textDecoration: "none",
                fontSize: 13,
              }}
            >
              {label}
            </a>
          ))}
        </nav>
      </Panel>

      <Panel title="이 대시보드의 목적">
        <div id="purpose" />
        <p style={{ marginTop: 0, lineHeight: 1.7 }}>
          일일소통현황 PDF를 자동으로 모아 데이터로 만들고, 업무담당자가 오늘 운영이 정상인지
          한눈에 판단하도록 돕는 통합관제 화면입니다.
        </p>
        <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8, color: palette.muted }}>
          <li>오늘 물량은 정상적으로 처리되고 있는가</li>
          <li>잔량, 인력, 운송, 설비, 안전에 이상징후가 있는가</li>
          <li>전일·최근 평균과 비교하면 어떤 변화가 있는가</li>
        </ul>
        <p style={{ marginBottom: 0, marginTop: 14, lineHeight: 1.7, color: palette.muted }}>
          PDF 원본 값은 바꾸지 않습니다. 검증에 실패한 데이터는 자동 수정하지 않고 상태로 표시합니다.
          AI 브리핑은 참고 자료이며, 최종 판단은 담당자가 합니다.
        </p>
      </Panel>

      <Panel title="화면 보는 법">
        <div id="howto" />
        <div style={{ display: "grid", gap: 10 }}>
          {[
            ["조회 일자", "왼쪽에서 날짜를 고릅니다. 보고서가 수집된 날짜만 선택할 수 있습니다."],
            ["비교 기준", "전일, 최근 7업무일 평균, 최근 30업무일 평균, 동일 요일 평균. KPI 옆 증감률에 반영됩니다."],
            ["소통 상태", "잔량 0이면 정상 소통(초록), 잔량이 있으면 잔량 발생(노랑)입니다."],
            ["상태 색", "정상=초록, 관심=파랑, 주의=노랑, 위험=빨강. 브리핑에서는 적정/관심/관리필요/위험으로 표시됩니다."],
            ["표시 단위", "물량은 기본적으로 천개입니다. 주말·공휴일 축약형 보고서는 일부 항목이 비어 있을 수 있습니다."],
          ].map(([label, text]) => (
            <div key={label} style={panelAltStyle(palette)}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>{label}</div>
              <div style={{ color: palette.muted, lineHeight: 1.6, fontSize: 14 }}>{text}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="주요 화면">
        <div id="screens" />
        <div style={{ display: "grid", gap: 12 }}>
          {SCREENS.map((screen) => (
            <div key={screen.path} style={panelAltStyle(palette)}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                <h4 style={{ margin: 0 }}>{screen.title}</h4>
                <Link
                  to={screen.path}
                  style={{
                    flexShrink: 0,
                    fontSize: 13,
                    color: palette.caution,
                    textDecoration: "none",
                    fontWeight: 600,
                  }}
                >
                  화면 열기
                </Link>
              </div>
              <p style={{ margin: "8px 0 6px", lineHeight: 1.6 }}>{screen.purpose}</p>
              <p style={{ margin: 0, color: palette.muted, fontSize: 14, lineHeight: 1.6 }}>{screen.look}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="주요 지표">
        <div id="metrics" />
        <div style={{ display: "grid", gap: 8 }}>
          {METRICS.map((metric) => (
            <div key={metric.name} className="imc-guide-metric" style={panelAltStyle(palette, { padding: "12px 14px" })}>
              <div>
                <div style={{ fontWeight: 700 }}>{metric.name}</div>
                <div style={{ color: palette.muted, fontSize: 12, marginTop: 4 }}>{metric.where}</div>
              </div>
              <div style={{ lineHeight: 1.6, fontSize: 14 }}>{metric.meaning}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
