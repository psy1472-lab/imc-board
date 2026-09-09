const SELECTED_DATE_KEY = "imc.selectedDate";
const SUMMARY_PREFIX = "imc.summary.";
const BRIEFING_PREFIX = "imc.briefing.core.";
const MAX_JSON_ENTRIES = 4;

function readJson<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
    prunePrefix(key.startsWith(SUMMARY_PREFIX) ? SUMMARY_PREFIX : BRIEFING_PREFIX, key);
  } catch {
    // quota or private mode
  }
}

function prunePrefix(prefix: string, keepKey: string) {
  const keys = Object.keys(sessionStorage).filter((item) => item.startsWith(prefix));
  if (keys.length <= MAX_JSON_ENTRIES) return;
  const extras = keys.filter((item) => item !== keepKey);
  extras.slice(0, keys.length - MAX_JSON_ENTRIES).forEach((item) => sessionStorage.removeItem(item));
}

export function readSelectedDate(): string {
  try {
    return sessionStorage.getItem(SELECTED_DATE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function writeSelectedDate(date: string) {
  try {
    if (date) {
      sessionStorage.setItem(SELECTED_DATE_KEY, date);
    }
  } catch {
    // ignore
  }
}

export function summarySessionKey(date: string, compareBasis: string) {
  return `${SUMMARY_PREFIX}${date}:${compareBasis}`;
}

export function readCachedSummary<T>(date: string, compareBasis: string): T | null {
  const value = readJson<T>(summarySessionKey(date, compareBasis));
  if (!value || typeof value !== "object") return null;
  const reportDate = (value as { meta?: { reportDate?: string } }).meta?.reportDate;
  return reportDate === date ? value : null;
}

export function writeCachedSummary(date: string, compareBasis: string, value: unknown) {
  writeJson(summarySessionKey(date, compareBasis), value);
}

export function readCachedBriefing<T>(date: string): T | null {
  const value = readJson<T>(`${BRIEFING_PREFIX}${date}`);
  if (!value || typeof value !== "object") return null;
  const reportDate = (value as { meta?: { reportDate?: string } }).meta?.reportDate;
  return reportDate === date ? value : null;
}

export function writeCachedBriefing(date: string, value: unknown) {
  writeJson(`${BRIEFING_PREFIX}${date}`, value);
}
