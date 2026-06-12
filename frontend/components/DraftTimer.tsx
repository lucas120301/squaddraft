"use client";

import { useEffect, useState } from "react";

export function DraftTimer({
  seconds,
  turnKey,
}: {
  seconds: number | null;
  turnKey: string;
}) {
  const [remaining, setRemaining] = useState(seconds ?? 0);

  useEffect(() => {
    setRemaining(seconds ?? 0);
  }, [seconds, turnKey]);

  useEffect(() => {
    const t = window.setInterval(() => {
      setRemaining((r) => (r > 0 ? r - 1 : 0));
    }, 1000);
    return () => window.clearInterval(t);
  }, [turnKey]);

  const urgent = remaining > 0 && remaining <= 5;
  const expired = remaining <= 0;

  return (
    <div className={`text-right ${urgent ? "animate-pulse" : ""}`}>
      <p
        className={`font-mono text-3xl font-bold tabular-nums ${
          expired ? "text-slate-500" : urgent ? "text-red-400" : "text-blue-400"
        }`}
      >
        {expired ? "—" : remaining}
      </p>
      <p className="text-[10px] uppercase tracking-widest text-slate-500">
        {expired ? "auto-picking" : "sec left"}
      </p>
    </div>
  );
}
