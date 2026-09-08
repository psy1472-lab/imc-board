import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { darkPalette, lightPalette, type ThemeMode, type ThemePalette } from "../styles/theme";

type ThemeContextValue = {
  mode: ThemeMode;
  palette: ThemePalette;
  toggleMode: () => void;
  setMode: (mode: ThemeMode) => void;
};

const STORAGE_KEY = "imc-dashboard-theme";

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getInitialMode(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(getInitialMode);

  const palette = mode === "dark" ? darkPalette : lightPalette;

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, mode);
    document.documentElement.dataset.theme = mode;
    document.body.style.backgroundColor = palette.bg;
    document.body.style.color = palette.text;
  }, [mode, palette.bg, palette.text]);

  const value = useMemo(
    () => ({
      mode,
      palette,
      toggleMode: () => setModeState((prev) => (prev === "dark" ? "light" : "dark")),
      setMode: setModeState,
    }),
    [mode, palette],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
