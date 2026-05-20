"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Evaluate" },
  { href: "/traces", label: "Traces" },
  { href: "/cost", label: "Cost" },
  { href: "/audit", label: "Audit" },
  { href: "/graph", label: "Graph" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        gap: "32px",
        padding: "16px 24px",
        borderBottom: "1px solid #222",
        background: "#0d0d14",
      }}
    >
      <Link
        href="/"
        style={{
          fontSize: "20px",
          fontWeight: 700,
          color: "#7c3aed",
          letterSpacing: "-0.5px",
        }}
      >
        TraceForge
      </Link>

      <div style={{ display: "flex", gap: "24px" }}>
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                fontSize: "14px",
                fontWeight: isActive ? 600 : 400,
                color: isActive ? "#e0e0e0" : "#888",
                borderBottom: isActive ? "2px solid #7c3aed" : "2px solid transparent",
                paddingBottom: "4px",
                transition: "color 0.2s",
              }}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
