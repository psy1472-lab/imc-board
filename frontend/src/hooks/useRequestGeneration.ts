import { useCallback, useRef } from "react";

/** Ignore stale responses when the inquiry date changes mid-request. */
export function useRequestGeneration() {
  const generation = useRef(0);

  const next = useCallback(() => {
    generation.current += 1;
    return generation.current;
  }, []);

  const isCurrent = useCallback((id: number) => id === generation.current, []);

  const invalidate = useCallback(() => {
    generation.current += 1;
  }, []);

  return { next, isCurrent, invalidate };
}
