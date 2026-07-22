"use client";

import { useEffect, useState } from "react";

/** UTC + IST operational clock. Ticks every second, hydration-safe. */
export function LiveClock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!now) return <span className="readout text-xs text-ink-dim">--:--:-- UTC</span>;

  const utc = now.toISOString().slice(11, 19);
  const ist = now.toLocaleTimeString("en-GB", {
    timeZone: "Asia/Kolkata",
    hour12: false,
  });

  return (
    <div className="flex items-center gap-3 readout text-xs">
      <span className="text-ink">
        {utc} <span className="text-ink-dim">UTC</span>
      </span>
      <span className="text-ink-dim">·</span>
      <span className="text-ink">
        {ist} <span className="text-ink-dim">IST</span>
      </span>
    </div>
  );
}
