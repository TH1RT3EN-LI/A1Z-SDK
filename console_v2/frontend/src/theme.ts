import type { ITheme } from "@xterm/xterm";

export type ThemeMode = "light" | "dark";

const THEME_STORAGE_KEY = "a1z-console-theme";

export function readThemeMode(): ThemeMode {
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (storedTheme === "light" || storedTheme === "dark") return storedTheme;
  } catch {
    // Storage can be unavailable in hardened browser contexts.
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function storeThemeMode(theme: ThemeMode) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // The in-memory selection still applies for the current session.
  }
}

export const terminalThemes: Record<ThemeMode, ITheme> = {
  light: {
    background: "#ffffff",
    foreground: "#1c1c1e",
    cursor: "#007aff",
    cursorAccent: "#ffffff",
    selectionBackground: "#007aff33",
    black: "#1c1c1e",
    red: "#ff3b30",
    green: "#34c759",
    yellow: "#ff9500",
    blue: "#007aff",
    magenta: "#af52de",
    cyan: "#32ade6",
    white: "#f2f2f7",
    brightBlack: "#8e8e93",
  },
  dark: {
    background: "#000000",
    foreground: "#f2f2f7",
    cursor: "#0a84ff",
    cursorAccent: "#ffffff",
    selectionBackground: "#0a84ff55",
    black: "#1c1c1e",
    red: "#ff453a",
    green: "#30d158",
    yellow: "#ff9f0a",
    blue: "#0a84ff",
    magenta: "#bf5af2",
    cyan: "#64d2ff",
    white: "#f2f2f7",
    brightBlack: "#8e8e93",
  },
};

export const viewportThemes = {
  light: {
    background: "#f2f2f7",
    fog: "#f2f2f7",
    hemisphereSky: "#ffffff",
    hemisphereGround: "#8e8e93",
    keyLight: "#ffffff",
    rimLight: "#007aff",
    gridMajor: "#8e8e93",
    gridMinor: "#d1d1d6",
  },
  dark: {
    background: "#000000",
    fog: "#000000",
    hemisphereSky: "#f2f2f7",
    hemisphereGround: "#1c1c1e",
    keyLight: "#ffffff",
    rimLight: "#0a84ff",
    gridMajor: "#636366",
    gridMinor: "#2c2c2e",
  },
} satisfies Record<ThemeMode, Record<string, string>>;
