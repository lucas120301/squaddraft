"use client";

import { DraftTimer } from "@/components/DraftTimer";
import { FormationPitch } from "@/components/FormationPitch";
import { SpinMachine } from "@/components/SpinMachine";
import {
  Auth,
  connectWs,
  getClubs,
  getFormations,
  getRoom,
  getSlotFits,
  loadAuth,
  makePick,
  parseWsRoomState,
  revealSpin,
  reroll,
  startDraft,
  updateLobby,
} from "@/lib/api";
import { ERAS } from "@/lib/constants";
import { RoomState, useRoomStore } from "@/stores/roomStore";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

function FitBadge({ label }: { label: string }) {
  const colors: Record<string, string> = {
    Natural: "text-emerald-400",
    Strong: "text-green-400",
    Usable: "text-yellow-400",
    Awkward: "text-orange-400",
    Bad: "text-red-400",
    "Cannot play": "text-red-600",
  };
  return <span className={`text-xs font-medium ${colors[label] || "text-slate-400"}`}>{label}</span>;
}

function Lobby({
  auth,
  state,
  formations,
  onRefresh,
}: {
  auth: Auth;
  state: RoomState;
  formations: { id: string; name: string }[];
  onRefresh: () => void;
}) {
  const me = state.players.find((p) => p.id === auth.roomPlayerId);
  const [formationId, setFormationId] = useState(me?.formation_id || "4-3-3");
  const [teamName, setTeamName] = useState(me?.team_name || me?.nickname || "");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function saveLobby() {
    try {
      await updateLobby(auth, formationId, teamName);
      setSaved(true);
      onRefresh();
      window.setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }

  async function handleStart() {
    try {
      await startDraft(auth);
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
    }
  }

  const allReady = state.players.length >= 2 && state.players.every((p) => p.formation_id);

  return (
    <div className="space-y-6">
      <div className="card p-8 text-center">
        <p className="text-xs font-bold uppercase tracking-[0.25em] text-slate-500">Room code</p>
        <p className="mt-2 font-mono text-5xl font-bold tracking-[0.35em] text-white">{state.room.code}</p>
        <p className="mt-3 text-sm text-slate-400">Share this code so friends can join</p>
      </div>

      <div className="card space-y-4 p-6">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-blue-400">Step 1</p>
          <p className="mt-1 text-lg font-semibold">Choose your formation</p>
        </div>
        <input
          className="input"
          placeholder="Team name (optional)"
          value={teamName}
          onChange={(e) => setTeamName(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {formations.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`rounded-xl border px-3 py-3 text-sm font-semibold transition ${
                formationId === f.id
                  ? "border-blue-500 bg-blue-950/50 text-blue-200"
                  : "border-slate-700 bg-slate-950/50 text-slate-300 hover:border-slate-500"
              }`}
              onClick={() => setFormationId(f.id)}
            >
              {f.name}
            </button>
          ))}
        </div>
        <button className="btn-secondary w-full" onClick={saveLobby}>
          {saved ? "Saved ✓" : "Save setup"}
        </button>
      </div>

      <div className="card p-5">
        <p className="mb-3 text-sm font-medium text-slate-300">Players in lobby ({state.players.length})</p>
        <ul className="space-y-2">
          {state.players.map((p) => (
            <li key={p.id} className="flex items-center justify-between rounded-lg bg-slate-950/50 px-3 py-2 text-sm">
              <span>
                {p.team_name || p.nickname}
                {p.is_host && <span className="ml-2 text-xs text-blue-400">host</span>}
              </span>
              <span className={p.formation_id ? "text-emerald-400" : "text-slate-500"}>
                {p.formation_id || "pick formation"}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {me?.is_host && (
        <button className="btn-primary w-full py-4 text-lg" disabled={!allReady} onClick={handleStart}>
          Start drafting →
        </button>
      )}
      {!allReady && (
        <p className="text-center text-xs text-slate-500">Need 2+ players, each with a formation saved</p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}

function DraftView({
  auth,
  state,
  formations,
  clubs,
  onRefresh,
}: {
  auth: Auth;
  state: RoomState;
  formations: { id: string; name: string; slots: { slot_id: string; position: string; x: number; y: number }[] }[];
  clubs: { id: string; name: string; short_name: string }[];
  onRefresh: () => void;
}) {
  const me = state.players.find((p) => p.id === auth.roomPlayerId);
  const isActive = state.active_room_player_id === auth.roomPlayerId;
  const selectedPlayerId = useRoomStore((s) => s.selectedPlayerId);
  const setSelectedPlayerId = useRoomStore((s) => s.setSelectedPlayerId);
  const setState = useRoomStore((s) => s.setState);
  const [error, setError] = useState("");
  const [slotFits, setSlotFits] = useState<Record<string, string>>({});
  const [boardReady, setBoardReady] = useState(false);
  const [spinning, setSpinning] = useState(false);
  const [picking, setPicking] = useState(false);

  const turnKey = `${state.active_room_player_id ?? "none"}:${state.room.current_pick_index}`;
  const spinRevealed = state.room.spin_revealed ?? false;
  const spinRound = state.room.spin_round ?? 1;
  const spinKey = state.current_spin
    ? `${spinRound}:${state.current_spin.club_id}:${state.current_spin.era}`
    : `${spinRound}:hidden`;
  const boardOpen = spinRevealed && boardReady;
  const prevSpinKey = useRef(spinKey);

  useEffect(() => {
    setSelectedPlayerId(null);
    setError("");
    setPicking(false);
    if (!spinRevealed) {
      setBoardReady(false);
      prevSpinKey.current = spinKey;
      return;
    }
    if (spinKey !== prevSpinKey.current) {
      prevSpinKey.current = spinKey;
      setBoardReady(false);
    }
  }, [turnKey, spinKey, spinRevealed, setSelectedPlayerId]);

  const myFormation = formations.find((f) => f.id === me?.formation_id);
  const filledSlots = new Set(me?.picks.map((p) => p.slot_id) || []);
  const openSlots = myFormation?.slots.filter((s) => !filledSlots.has(s.slot_id)) || [];
  const pickNum = (me?.picks.length || 0) + 1;
  const activePlayer = state.players.find((p) => p.id === state.active_room_player_id);

  const viewPlayer = useMemo(() => {
    if (isActive) return me;
    return activePlayer;
  }, [isActive, me, activePlayer]);

  const viewFormation = formations.find((f) => f.id === viewPlayer?.formation_id);

  useEffect(() => {
    if (!selectedPlayerId || openSlots.length === 0 || !isActive || !boardOpen) {
      setSlotFits({});
      return;
    }
    getSlotFits(auth, selectedPlayerId, openSlots.map((s) => s.slot_id)).then((d) => {
      const map: Record<string, string> = {};
      d.fits.forEach((f) => {
        map[f.slot_id] = f.label;
      });
      setSlotFits(map);
    });
  }, [auth, selectedPlayerId, openSlots.length, isActive, boardOpen]);

  async function handleSpin() {
    setSpinning(true);
    setError("");
    try {
      const next = await revealSpin(auth);
      setState(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Spin failed");
    } finally {
      setSpinning(false);
    }
  }

  async function handlePick(slotId: string) {
    if (!selectedPlayerId || picking) return;
    setPicking(true);
    setError("");
    try {
      const next = await makePick(auth, selectedPlayerId, slotId);
      setState(next);
      setSelectedPlayerId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Pick failed");
    } finally {
      setPicking(false);
    }
  }

  async function handleReroll() {
    setError("");
    try {
      const next = await reroll(auth);
      setState(next);
      setBoardReady(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reroll failed");
    }
  }

  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center justify-between gap-4 p-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-500">
            Spin round {spinRound} · Your pick {pickNum}/{state.room.total_rounds}
          </p>
          <p className="mt-1 text-lg font-semibold">
            {!spinRevealed ? (
              isActive ? (
                <span className="text-amber-300">Your turn — spin the wheel</span>
              ) : (
                <span>
                  Waiting for <span className="text-blue-300">{activePlayer?.nickname}</span> to spin
                </span>
              )
            ) : isActive ? (
              <span className="text-amber-300">Your turn — make your pick</span>
            ) : (
              <span>
                <span className="text-blue-300">{activePlayer?.nickname}</span> is picking
              </span>
            )}
          </p>
        </div>
        <DraftTimer seconds={state.room.timer_seconds_remaining} turnKey={turnKey} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_200px]">
        <div className="space-y-4">
          <SpinMachine
            key={spinKey}
            spin={state.current_spin}
            spinRevealed={spinRevealed}
            clubs={clubs}
            eras={[...ERAS]}
            isActive={isActive}
            activeName={activePlayer?.nickname || "opponent"}
            spinning={spinning}
            onSpinRequest={handleSpin}
            onRevealComplete={() => setBoardReady(true)}
          />

          {boardOpen && (
            <>
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-300">
                  {isActive ? "Pick a player" : `${activePlayer?.nickname} is picking`}
                </p>
                {isActive &&
                  (me?.normal_rerolls_left ?? 0) > 0 &&
                  state.room.current_pick_index % (state.room.player_count || 1) === 0 && (
                  <button type="button" className="btn-secondary text-xs" onClick={handleReroll} disabled={picking}>
                    Re-spin ({me?.normal_rerolls_left})
                  </button>
                )}
              </div>

              <div
                className={`card grid max-h-[280px] gap-1.5 overflow-y-auto p-2 sm:grid-cols-2 transition-opacity ${!isActive || picking ? "pointer-events-none opacity-45" : ""}`}
              >
                {state.available_players.length === 0 ? (
                  <p className="col-span-2 p-3 text-center text-sm text-slate-500">No eligible players</p>
                ) : (
                  state.available_players.map((pl) => (
                    <button
                      key={pl.id}
                      type="button"
                      className={`rounded-lg border px-2.5 py-2 text-left transition ${
                        selectedPlayerId === pl.id
                          ? "border-amber-400 bg-amber-950/30"
                          : "border-slate-800 bg-slate-950/60 hover:border-slate-600"
                      }`}
                      disabled={picking}
                      onClick={() => isActive && !picking && setSelectedPlayerId(pl.id)}
                    >
                      <p className="truncate text-sm font-semibold">{pl.name}</p>
                      <p className="text-[11px] text-slate-400">
                        {pl.positions_label || pl.primary_position}
                      </p>
                    </button>
                  ))
                )}
              </div>

              {isActive && selectedPlayerId && openSlots.length > 0 && (
                <div className="card p-3">
                  <p className="mb-2 text-xs font-medium text-slate-400">Assign to slot</p>
                  <div className="flex flex-wrap gap-1.5">
                    {openSlots.map((s) => (
                      <button
                        key={s.slot_id}
                        type="button"
                        className="btn-secondary flex min-w-[64px] flex-col items-center gap-0.5 px-2 py-1.5 text-xs"
                        disabled={picking}
                        onClick={() => handlePick(s.slot_id)}
                      >
                        <span className="font-bold">{s.position}</span>
                        {slotFits[s.slot_id] && <FitBadge label={slotFits[s.slot_id]} />}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {error && <p className="text-sm text-red-400">{error}</p>}
            </>
          )}
        </div>

        <div className="card p-3">
          {viewFormation ? (
            <FormationPitch
              formationName={isActive ? viewFormation.name : `${viewPlayer?.nickname} · ${viewFormation.name}`}
              slots={viewFormation.slots}
              picks={viewPlayer?.picks.map((p) => ({ slot_id: p.slot_id, name: p.name })) || []}
            />
          ) : (
            <p className="text-sm text-slate-500">No formation</p>
          )}
        </div>
      </div>
    </div>
  );
}

function Results({ state, meId }: { state: RoomState; meId: string }) {
  const mePlayer = state.players.find((p) => p.id === meId);
  const me = mePlayer
    ? state.records.find((r) => r.nickname === mePlayer.nickname || r.team_name === (mePlayer.team_name || mePlayer.nickname))
    : undefined;
  const top = state.records[0];

  return (
    <div className="space-y-6">
      {me && (
        <div className="card p-8 text-center">
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-slate-500">Your projected record</p>
          <p className="mt-4 font-mono text-6xl font-bold tracking-tight text-white">{me.record}</p>
          <p className="mt-2 text-sm text-slate-400">W · D · L over 38 games</p>
          <p className="mt-4 text-lg font-semibold text-amber-300/90">
            {me.wins >= 30 ? "Title contenders" : me.wins >= 20 ? "European push" : me.wins >= 12 ? "Mid-table" : "Relegation scrap"}
          </p>
        </div>
      )}

      <div className="card p-6">
        <h2 className="text-lg font-bold">Final standings</h2>
        <ul className="mt-4 space-y-3">
          {state.records.map((r, i) => (
            <li
              key={r.nickname}
              className={`flex items-center justify-between rounded-xl px-4 py-3 ${
                i === 0 ? "border border-amber-500/30 bg-amber-950/20" : "bg-slate-950/40"
              }`}
            >
              <span className="flex items-center gap-3">
                <span className="text-sm text-slate-500">#{i + 1}</span>
                <span className="font-medium">{r.team_name}</span>
              </span>
              <span className="font-mono text-xl font-bold">{r.record}</span>
            </li>
          ))}
        </ul>
        {top && (
          <p className="mt-6 text-center text-sm text-slate-400">
            Champion: <span className="font-semibold text-amber-300">{top.team_name}</span> ({top.record})
          </p>
        )}
      </div>
    </div>
  );
}

export default function RoomPage() {
  const params = useParams();
  const code = (params.code as string).toUpperCase();
  const [auth, setAuth] = useState<Auth | null>(null);
  const state = useRoomStore((s) => s.state);
  const formations = useRoomStore((s) => s.formations);
  const setState = useRoomStore((s) => s.setState);
  const setFormations = useRoomStore((s) => s.setFormations);
  const [clubs, setClubs] = useState<{ id: string; name: string; short_name: string }[]>([]);

  const refresh = useCallback(async () => {
    const data = await getRoom(code);
    setState(data);
  }, [code, setState]);

  useEffect(() => {
    const a = loadAuth(code);
    if (a) setAuth(a);
    getFormations().then((d) => setFormations(d.formations));
    getClubs().then((d) => setClubs(d.clubs)).catch(() => setClubs([]));
    refresh();
  }, [code, refresh, setFormations]);

  useEffect(() => {
    if (!auth) return;
    const ws = connectWs(auth, (msg) => {
      const next = parseWsRoomState(msg);
      if (next) setState(next);
    });
    const interval = setInterval(refresh, 30000);
    return () => {
      ws.close();
      clearInterval(interval);
    };
  }, [auth, refresh, setState]);

  if (!auth || !state) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-slate-400">Loading room…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl p-4 pb-12">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">PL Era Draft</h1>
          <p className="text-xs text-slate-500">Spin club + era · draft your XI</p>
        </div>
        <span className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 font-mono text-sm tracking-widest">
          {code}
        </span>
      </header>

      {state.room.status === "lobby" && (
        <Lobby auth={auth} state={state} formations={formations} onRefresh={refresh} />
      )}
      {state.room.status === "drafting" && (
        <DraftView auth={auth} state={state} formations={formations} clubs={clubs} onRefresh={refresh} />
      )}
      {state.room.status === "simulating" && (
        <div className="card flex min-h-[280px] flex-col items-center justify-center gap-4 p-10 text-center">
          <div className="h-12 w-12 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
          <p className="text-lg font-medium">Simulating 38-game season…</p>
          <p className="text-sm text-slate-500">Projecting W-D-L from your drafted XI</p>
        </div>
      )}
      {state.room.status === "complete" && <Results state={state} meId={auth.roomPlayerId} />}
    </main>
  );
}
