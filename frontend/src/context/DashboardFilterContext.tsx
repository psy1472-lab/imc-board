import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fetchReportDates, fetchDashboardSummary } from "../lib/api";
import {
  compareToTrendView,
  trendViewToCompare,
  type CompareBasis,
} from "../lib/dashboardCompare";
import type { DashboardSummary } from "../types/dashboard";
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
  loadDashboardSummary: (date: string, compareBasis?: CompareBasis) => Promise<DashboardSummary>;
  getCachedDashboardSummary: (date: string, compareBasis?: CompareBasis) => DashboardSummary | null;
};

const DashboardFilterContext = createContext<DashboardFilterContextValue | null>(null);

function summaryCacheKey(date: string, compareBasis: CompareBasis) {
  return `${date}:${compareBasis}`;
}

export function DashboardFilterProvider({ children }: { children: ReactNode }) {
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [compare, setCompare] = useState<CompareBasis>("prev_day");
  const [trendView, setTrendView] = useState<VolumeTrendView>("30d");
  const [error, setError] = useState<string | null>(null);
  const summaryCacheRef = useRef<Map<string, DashboardSummary>>(new Map());
  const inflightSummaryRef = useRef<Map<string, Promise<DashboardSummary>>>(new Map());

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

  const getCachedDashboardSummary = useCallback((date: string, compareBasis: CompareBasis = "prev_day") => {
    return summaryCacheRef.current.get(summaryCacheKey(date, compareBasis)) ?? null;
  }, []);

  const loadDashboardSummary = useCallback(
    async (date: string, compareBasis: CompareBasis = "prev_day") => {
      const key = summaryCacheKey(date, compareBasis);
      const cached = summaryCacheRef.current.get(key);
      if (cached) {
        return cached;
      }
      const inflight = inflightSummaryRef.current.get(key);
      if (inflight) {
        return inflight;
      }
      const request = fetchDashboardSummary(date, compareBasis)
        .then((summary) => {
          summaryCacheRef.current.set(key, summary);
          inflightSummaryRef.current.delete(key);
          return summary;
        })
        .catch((err) => {
          inflightSummaryRef.current.delete(key);
          throw err;
        });
      inflightSummaryRef.current.set(key, request);
      return request;
    },
    [],
  );

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
      loadDashboardSummary,
      getCachedDashboardSummary,
    }),
    [
      dates,
      selectedDate,
      compare,
      setCompareBasis,
      trendView,
      setVolumeTrendView,
      error,
      refreshDates,
      loadDashboardSummary,
      getCachedDashboardSummary,
    ],
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
