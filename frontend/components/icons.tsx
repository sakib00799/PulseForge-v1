import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "overview" | "incidents" | "events" | "services" | "team"
  | "security" | "audit" | "menu" | "close" | "arrow" | "refresh"
  | "logout" | "check" | "activity";

const paths: Record<IconName, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  incidents: <><path d="M12 3 2.8 19a1.5 1.5 0 0 0 1.3 2.2h15.8a1.5 1.5 0 0 0 1.3-2.2L12 3Z" /><path d="M12 9v5" /><path d="M12 18h.01" /></>,
  events: <><path d="M3 12h4l3-7 4 14 3-7h4" /></>,
  services: <><rect x="3" y="4" width="18" height="7" rx="2" /><rect x="3" y="13" width="18" height="7" rx="2" /><path d="M7 7.5h.01M7 16.5h.01M11 7.5h6M11 16.5h6" /></>,
  team: <><path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-6A3.5 3.5 0 0 0 3 18.5V20" /><circle cx="9.5" cy="8" r="3" /><path d="M17 5.2a3 3 0 0 1 0 5.6M21 20v-1.5a3.5 3.5 0 0 0-2.8-3.4" /></>,
  security: <><path d="M12 2 4 5v6c0 5.2 3.3 8.7 8 11 4.7-2.3 8-5.8 8-11V5l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
  audit: <><path d="M8 3h9a2 2 0 0 1 2 2v15a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6l3-3Z" /><path d="M8 3v4h4M9 12h6M9 16h6" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  close: <><path d="M5 5 19 19M19 5 5 19" /></>,
  arrow: <><path d="M5 12h14m-6-6 6 6-6 6" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.6-4.5L3 9m0-6v6h6M4 13a8 8 0 0 0 14.6 4.5L21 15m0 6v-6h-6" /></>,
  logout: <><path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5M15 16l4-4-4-4M8 12h11" /></>,
  check: <><path d="m5 12 4 4L19 6" /></>,
  activity: <><path d="M3 12h4l3-7 4 14 3-7h4" /></>,
};

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return <svg aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" {...props}>{paths[name]}</svg>;
}
