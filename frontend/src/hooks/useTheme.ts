import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const KEY = "pomar-theme";

function systemPrefersDark(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
  );
}

function readStored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

/** Aplica o tema no <html data-theme>. Default = preferência do sistema. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(
    () => readStored() ?? (systemPrefersDark() ? "dark" : "light"),
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(KEY, next);
      } catch {
        /* ignora storage indisponível */
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
