export type BriefingItem = {
  label: string;
  value?: string | number | null;
  unit?: string;
  text?: string | null;
  status?: string;
  statusLabel?: string;
  assessment?: string | null;
  trend?: string | null;
  trendPercent?: number | null;
};

export type BriefingSection = {
  title: string;
  overallStatus?: string;
  overallLabel?: string;
  assessment?: string;
  gaps?: string[];
  items: BriefingItem[];
};

export type BriefingHighlight = {
  severity: string;
  category?: string;
  message: string;
};

export type BriefingChangeItem = {
  label: string;
  text: string;
  trend?: string;
  percent?: number;
};

export type DailyBriefing = {
  meta: {
    reportDate: string;
    centerName?: string;
    compareBasis?: string;
    compareLabel?: string;
    communicationStatus?: string;
    generatedAt: string;
    source: string;
  };
    sections: {
    todayOperation: BriefingSection;
    majorChanges: { title: string; items: BriefingChangeItem[] };
    staffing: BriefingSection;
    transport: BriefingSection;
    equipment: BriefingSection;
    safety: BriefingSection;
  };
  highlights: BriefingHighlight[];
  tomorrowOutlook?: {
    title: string;
    items: Array<{ label: string; text: string }>;
  };
  disclaimer?: string;
};
