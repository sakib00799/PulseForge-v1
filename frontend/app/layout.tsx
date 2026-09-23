import type { Metadata } from "next";
import "./globals.css";
import "./dashboard.css";
import "./modern.css";
import "./dark.css";

export const metadata: Metadata = {
  title: "PulseForge | Incident Intelligence",
  description: "Real-time incident intelligence and automated recovery."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: `(function(){try{var t=localStorage.getItem('pulseforge-theme');document.documentElement.dataset.theme=t==='light'||t==='dark'?t:(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(e){document.documentElement.dataset.theme='light'}})();` }} /></head>
      <body>{children}</body>
    </html>
  );
}
