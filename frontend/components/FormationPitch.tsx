"use client";

type Slot = { slot_id: string; position: string; x: number; y: number };
type Pick = { slot_id: string; name: string; primary_position?: string };

function playerInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ""}${parts[parts.length - 1][0] ?? ""}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function shortName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return parts[parts.length - 1];
  return name;
}

export function FormationPitch({
  formationName,
  slots,
  picks,
  highlightSlotId,
}: {
  formationName: string;
  slots: Slot[];
  picks: Pick[];
  highlightSlotId?: string | null;
}) {
  const pickBySlot = Object.fromEntries(picks.map((p) => [p.slot_id, p]));

  return (
    <div>
      <p className="mb-2 text-xs font-medium text-slate-400">{formationName}</p>
      <div className="pitch">
        <div className="pitch-line" />
        <div
          className="pointer-events-none absolute inset-x-6 top-[18%] border-t border-emerald-700/20"
        />
        <div
          className="pointer-events-none absolute inset-x-10 top-[38%] rounded-full border border-emerald-700/15"
          style={{ aspectRatio: "1.6" }}
        />
        {slots.map((s) => {
          const pick = pickBySlot[s.slot_id];
          const active = highlightSlotId === s.slot_id;
          return (
            <div
              key={s.slot_id}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${s.x}%`, top: `${s.y}%` }}
            >
              {pick ? (
                <div className="flex w-11 flex-col items-center gap-0.5">
                  <div className="pitch-shirt">{playerInitials(pick.name)}</div>
                  <p className="max-w-[52px] truncate text-center text-[8px] font-medium leading-tight text-slate-200">
                    {shortName(pick.name)}
                  </p>
                </div>
              ) : (
                <div
                  className={`pitch-slot-empty ${active ? "pitch-slot-empty--active" : ""}`}
                  title={s.position}
                >
                  {s.position}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
