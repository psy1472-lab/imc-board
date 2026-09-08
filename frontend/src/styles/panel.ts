import type { CSSProperties } from "react";
import type { ThemePalette } from "./theme";

export function panelStyle(palette: ThemePalette, overrides?: CSSProperties): CSSProperties {
  return {
    background: palette.panel,
    border: `1px solid ${palette.border}`,
    borderRadius: 14,
    padding: 16,
    ...overrides,
  };
}

export function panelAltStyle(palette: ThemePalette, overrides?: CSSProperties): CSSProperties {
  return {
    background: palette.panelAlt,
    border: `1px solid ${palette.border}`,
    borderRadius: 12,
    padding: 14,
    ...overrides,
  };
}
