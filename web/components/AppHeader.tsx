"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CompassMark } from "./icons";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Live decision" },
  { href: "/replay", label: "Track record" },
];

export function AppHeader() {
  const pathname = usePathname();
  return (
    <header className="flex items-center justify-between gap-x-4 gap-y-3 flex-wrap py-6 border-b border-line">
      <div className="flex items-center gap-3">
        <span className="text-brand-2"><CompassMark size={24} /></span>
        <div className="leading-tight">
          <div className="flex items-center gap-2">
            <span className="text-[17px] font-semibold tracking-[-0.01em] text-ink">Compass</span>
            <span className="chip">Forecast decisions</span>
          </div>
          <div className="text-[12px] text-ink-3">Adjust the forecast with confidence</div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <nav className="flex items-center gap-1 rounded-lg p-1 border border-line bg-[rgba(255,255,255,0.02)]">
          {NAV.map((n) => {
            const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className="px-3 py-1.5 rounded-md text-[13px] font-medium transition-colors"
                style={
                  active
                    ? { background: "var(--color-brand)", color: "#fff" }
                    : { color: "var(--color-ink-3)" }
                }
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
