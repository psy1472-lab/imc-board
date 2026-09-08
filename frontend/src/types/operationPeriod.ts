export type OperationPeriodType =
  | "post_shopping_discount"
  | "special_communication"
  | "no_parcel_day";

export type OperationPeriod = {
  id: number;
  periodType: OperationPeriodType;
  startDate: string;
  endDate: string;
  note?: string | null;
  createdAt: string;
};

export const OPERATION_PERIOD_LABELS: Record<OperationPeriodType, string> = {
  post_shopping_discount: "우체국쇼핑할인",
  special_communication: "특별소통기간",
  no_parcel_day: "위탁배달원 하계 휴식기간",
};

export const OPERATION_PERIOD_DESCRIPTIONS: Record<OperationPeriodType, string> = {
  post_shopping_discount: "우체국쇼핑 할인 행사 기간",
  special_communication: "물량·소통 분석 시 참고할 특별 소통 기간",
  no_parcel_day: "위탁배달원 하계 휴식 기간(물량·소통 분석 참고)",
};
