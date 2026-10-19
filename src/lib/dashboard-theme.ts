export type DashboardTheme = "dark" | "light";

const KEY = "synora.dashboardTheme";

export function readDashboardTheme(): DashboardTheme {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Sets data-theme on <html> so portals (modals, toasts) inherit it too. */
export function applyDashboardTheme(theme: DashboardTheme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

export function clearDashboardTheme(): void {
  document.documentElement.removeAttribute("data-theme");
}

export function saveDashboardTheme(theme: DashboardTheme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // storage blocked: choice lasts for this session only
  }
  applyDashboardTheme(theme);
}
