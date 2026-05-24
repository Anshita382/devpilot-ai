import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "DevPilot AI",
  description: "Local-first multi-agent engineering operating system",
};

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/repos", label: "Repositories" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/*
          Fonts load from Google's CDN when online and fall back gracefully to
          high-quality system fonts (defined in globals.css) when offline — so
          the app builds and runs in fully air-gapped environments too.
        */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..700;1,9..144,400..600&family=JetBrains+Mono:wght@400;500&family=Manrope:wght@300..700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="min-h-screen">
          <header className="sticky top-0 z-40 border-b hairline bg-ink-950/80 backdrop-blur-xl">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
              <Link href="/dashboard" className="group flex items-baseline gap-3">
                <span className="font-display text-2xl font-semibold italic tracking-tight text-bone">
                  DevPilot
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-ember">
                  AI
                </span>
              </Link>
              <nav className="flex items-center gap-1">
                {NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="rounded-md px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-mist transition-colors hover:bg-ink-800 hover:text-bone"
                  >
                    {n.label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-6 py-10">{children}</main>
          <footer className="mx-auto max-w-7xl px-6 py-10">
            <div className="border-t hairline pt-6 font-mono text-[10px] uppercase tracking-[0.25em] text-mist">
              DevPilot AI · local-first · runs in mock mode with zero external services
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
