export const BEFORE_18_SLOT = "~18";

export const HOUR_SLOTS = [
  BEFORE_18_SLOT,
  "18",
  "19",
  "20",
  "21",
  "22",
  "23",
  "00",
  "01",
  "02",
  "03",
  "04",
  "05",
  "06",
] as const;

export function normalizeHourSlot(slot: string) {
  if (slot === BEFORE_18_SLOT) {
    return BEFORE_18_SLOT;
  }
  return slot.padStart(2, "0");
}

export function formatHourLabel(slot: string) {
  const normalized = normalizeHourSlot(slot);
  if (normalized === BEFORE_18_SLOT) {
    return "~18";
  }
  return `${normalized}~`;
}

export function buildHourlySeries<T extends { slot: string }>(
  rows: T[],
  fill: (slot: string) => T,
): T[] {
  const bySlot = new Map(rows.map((row) => [normalizeHourSlot(row.slot), row]));
  return HOUR_SLOTS.map((slot) => {
    const existing = bySlot.get(slot);
    return existing ?? fill(slot);
  });
}
