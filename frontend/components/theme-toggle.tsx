"use client";

import { useEffect, useState } from "react";

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
    const followSystem = () => {
      try {
        if (localStorage.getItem("pulseforge-theme")) return;
      } catch { return; }
      document.documentElement.dataset.theme = media.matches ? "dark" : "light";
      sync();
    };
    sync();
    media.addEventListener("change", followSystem);
    return () => media.removeEventListener("change", followSystem);
  }, []);

  function toggle() {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try { localStorage.setItem("pulseforge-theme", next); } catch { /* Theme still changes for this visit. */ }
  }

  return <button className={`theme-toggle${compact ? " compact" : ""}`} type="button" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
    <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
    {!compact && <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>}
  </button>;
}
