import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchReportDates } from "../lib/api";
import {
  compareToTrendView,
  trendViewToCompare,
  type CompareBasis,
} from "../lib/dashboardCompare";
import type { VolumeTrendView } from "../types/volumeAnalysis";

type DashboardFilterContextValue = {
  dates: string[];
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  compare: CompareBasis;
  setCompareBasis: (compare: CompareBasis) => void;
  trendView: VolumeTrendView;
  setVolumeTrendView: (trendView: VolumeTrendView) => void;
  error: string | null;
  refreshDates: () => Promise<void>;
};

const DashboardFilterContext = createContext<DashboardFilterContextValue | null>(null);

export function DashboardFilterProvider({ children }: { children: ReactNode }) {
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [compare, setCompare] = useState<CompareBasis>("prev_day");
  const [trendView, setTrendView] = useState<VolumeTrendView>("30d");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReportDates()
      .then((items) => {
        setDates(items);
        setSelectedDate(items[items.length - 1] ?? "");
      })
      .catch(() => setError("보고서 날짜를 불러오지 못했습니다."));
  }, []);

  const setCompareBasis = useCallback((nextCompare: CompareBasis) => {
    setCompare(nextCompare);
    const nextTrend = compareToTrendView(nextCompare);
    if (nextTrend) {
      setTrendView(nextTrend);
    }
  }, []);

  const setVolumeTrendView = useCallback((nextTrendView: VolumeTrendView) => {
    setTrendView(nextTrendView);
    setCompare(trendViewToCompare(nextTrendView));
  }, []);

  const refreshDates = useCallback(async () => {
    const items = await fetchReportDates();
    setDates(items);
    setSelectedDate((current) => {
      if (current && items.includes(current)) return current;
      return items[items.length - 1] ?? "";
    });
  }, []);

  const value = useMemo(
    () => ({
      dates,
      selectedDate,
      setSelectedDate,
      compare,
      setCompareBasis,
      trendView,
      setVolumeTrendView,
      error,
      refreshDates,
    }),
    [dates, selectedDate, compare, setCompareBasis, trendView, setVolumeTrendView, error, refreshDates],
  );

  return <DashboardFilterContext.Provider value={value}>{children}</DashboardFilterContext.Provider>;
}

export function useDashboardFilters() {
  const context = useContext(DashboardFilterContext);
  if (!context) {
    throw new Error("useDashboardFilters must be used within DashboardFilterProvider");
  }
  return context;
}
