export type NavItem = {
  label: string;
  path: string;
  ready: boolean;
  adminOnly?: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { label: "종합상황판", path: "/", ready: true },
  { label: "물량·소통 분석", path: "/volume", ready: true },
  { label: "인력·생산성 분석", path: "/staffing", ready: true },
  { label: "운송 관제", path: "/transport", ready: true },
  { label: "설비·구분기 분석", path: "/equipment", ready: true },
  { label: "안전·이상징후", path: "/safety", ready: true },
  { label: "AI 운영 브리핑", path: "/briefing", ready: true },
  { label: "보고서·다운로드", path: "/reports", ready: true, adminOnly: true },
  { label: "시스템 관리", path: "/settings", ready: true, adminOnly: true },
];

export const GUIDE_NAV_ITEM: NavItem = { label: "사용자 가이드", path: "/guide", ready: true };
