import Link from "next/link";
import { StatusDot } from "./status-dot";

const LINKS = [
  { href: "/", label: "What changed" },
  { href: "/duty", label: "Duty maps" },
  { href: "/queue", label: "Approval queue" },
  { href: "/org", label: "Organisation" },
  { href: "/loop", label: "Loop" },
  { href: "/mcp", label: "MCP" },
  { href: "/eval", label: "Eval" },
  { href: "/how-it-works", label: "How it works" },
];

export function SiteHeader() {
  return (
    <header className="border-b border-black/10 bg-[var(--color-surface)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Link
            href="/"
            className="font-[family-name:var(--font-heading)] text-xl text-[var(--color-accent)]"
          >
            Recontact
          </Link>
          <nav className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
            {LINKS.map((link) => (
              <Link key={link.href} href={link.href} className="hover:text-[var(--color-accent)]">
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusDot />
          <span className="text-sm">Demo lab (fictional)</span>
          <button
            type="button"
            className="rounded-full bg-[var(--color-accent)] px-3 py-1 text-sm text-white"
          >
            Try it as the lab
          </button>
        </div>
      </div>
    </header>
  );
}
