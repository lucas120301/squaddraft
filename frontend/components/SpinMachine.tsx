"use client";

import { CLUB_COLORS } from "@/lib/constants";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type SpinTarget = {
  club_id: string;
  club_name: string;
  era: string;
};

type ClubOption = { id: string; name: string; short_name?: string };

type Phase = "idle" | "spinning" | "landed";

function buildReel<T>(items: T[], target: T, loops = 3): T[] {
  const out: T[] = [];
  for (let i = 0; i < loops; i += 1) out.push(...items);
  out.push(target);
  return out;
}

function SpinReel<T extends string>({
  label,
  items,
  target,
  phase,
  accent,
}: {
  label: string;
  items: T[];
  target: T;
  phase: Phase;
  accent?: string;
}) {
  const reel = useMemo(() => buildReel(items, target), [items, target]);
  const targetIndex = reel.length - 1;
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    if (phase === "idle") {
      setOffset(0);
      return;
    }
    if (phase === "spinning") {
      setOffset(0);
      const t = window.setTimeout(() => setOffset(targetIndex), 80);
      return () => window.clearTimeout(t);
    }
    setOffset(targetIndex);
  }, [phase, targetIndex]);

  return (
    <div className="flex-1">
      <p className="mb-2 text-center text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <div className="spin-reel-window">
        <div
          className="pointer-events-none absolute inset-x-0 top-1/2 z-10 -translate-y-1/2 border-y border-amber-400/40 bg-amber-400/5"
          style={{ height: 56 }}
        />
        <div className="spin-reel-track" style={{ transform: `translateY(-${offset * 56}px)` }}>
          {reel.map((item, i) => (
            <div
              key={`${item}-${i}`}
              className="spin-reel-item"
              style={i === targetIndex && phase === "landed" && accent ? { color: accent } : undefined}
            >
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SpinMachine({
  spin,
  spinRevealed,
  clubs,
  eras,
  isActive,
  activeName,
  spinning,
  onSpinRequest,
  onRevealComplete,
}: {
  spin: SpinTarget | null;
  spinRevealed: boolean;
  clubs: ClubOption[];
  eras: string[];
  isActive: boolean;
  activeName: string;
  spinning: boolean;
  onSpinRequest: () => void;
  onRevealComplete: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const revealedRef = useRef<string | null>(null);

  const clubLabels = useMemo(() => clubs.map((c) => c.short_name || c.name), [clubs]);
  const clubDisplay = spin
    ? clubs.find((c) => c.id === spin.club_id)?.short_name || spin.club_name
    : "—";
  const accent = spin ? CLUB_COLORS[spin.club_id] || "#60a5fa" : undefined;
  const spinToken = spin ? `${spin.club_id}:${spin.era}` : null;

  const finishSpin = useCallback(() => {
    setPhase("landed");
    onRevealComplete();
  }, [onRevealComplete]);

  const startSpin = useCallback(() => {
    if (!spin) return;
    setPhase("spinning");
    window.setTimeout(finishSpin, 1600);
  }, [spin, finishSpin]);

  useEffect(() => {
    if (!spinRevealed || !spin || !spinToken) {
      setPhase("idle");
      revealedRef.current = null;
      return;
    }
    if (revealedRef.current === spinToken) return;
    revealedRef.current = spinToken;
    startSpin();
  }, [spinRevealed, spin, spinToken, startSpin]);

  if (!spinRevealed) {
    return (
      <div className="card flex min-h-[200px] flex-col items-center justify-center gap-3 p-8 text-center">
        {isActive ? (
          <>
            <p className="text-sm text-slate-400">You&apos;re up — spin for club &amp; era</p>
            <button
              type="button"
              className="btn-primary w-full max-w-xs py-3.5 text-base tracking-wide disabled:opacity-60"
              disabled={spinning}
              onClick={onSpinRequest}
            >
              {spinning ? "Spinning…" : "SPIN"}
            </button>
          </>
        ) : (
          <p className="text-sm text-slate-400">
            Waiting for <span className="font-semibold text-blue-300">{activeName}</span> to spin…
          </p>
        )}
      </div>
    );
  }

  if (!spin) {
    return (
      <div className="card flex min-h-[200px] items-center justify-center p-8 text-slate-500">
        Loading spin…
      </div>
    );
  }

  return (
    <div className="card overflow-hidden p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Club · Era</p>
        {phase === "landed" && (
          <div
            className="rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
            style={{ backgroundColor: `${accent}22`, color: accent, border: `1px solid ${accent}55` }}
          >
            {clubDisplay} · {spin.era}
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <SpinReel
          label="Club"
          items={clubLabels.length ? clubLabels : [clubDisplay]}
          target={clubDisplay}
          phase={phase}
          accent={accent}
        />
        <SpinReel label="Era" items={eras.length ? eras : [spin.era]} target={spin.era} phase={phase} accent="#fbbf24" />
      </div>

      {phase === "spinning" && (
        <p className="mt-5 text-center text-sm font-medium text-amber-300/90 animate-pulse">Spinning…</p>
      )}

      {phase === "landed" && isActive && (
        <p className="mt-5 text-center text-xs text-slate-400">
          Pick from <span className="font-semibold text-slate-200">{spin.club_name}</span>
        </p>
      )}
    </div>
  );
}
