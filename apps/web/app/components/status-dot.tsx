"use client";

import { useEffect, useState } from "react";

type Health = {
  falkordb?: string;
  kb?: { loading?: unknown };
  ncbi?: string;
};

type Tone = "up" | "degraded" | "down";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function StatusDot() {
  const [tone, setTone] = useState<Tone>("down");

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const response = await fetch(`${API}/api/health`);
        if (!response.ok) throw new Error("health");
        const body = (await response.json()) as Health;
        if (cancelled) return;
        if (body.falkordb !== "up") setTone("down");
        else if (body.kb?.loading || body.ncbi === "degraded") setTone("degraded");
        else setTone("up");
      } catch {
        if (!cancelled) setTone("down");
      }
    }
    void poll();
    const timer = setInterval(() => void poll(), 15000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const color = tone === "up" ? "#1f9d55" : tone === "degraded" ? "#d9a21b" : "#d64545";
  return (
    <span className="inline-flex items-center gap-2 text-sm text-[var(--color-muted)]">
      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {tone === "down" ? "The graph database is restarting. Try again in a minute." : "Graph"}
    </span>
  );
}
