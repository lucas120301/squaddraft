"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createRoom, joinRoom, saveAuth } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [nickname, setNickname] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleCreate() {
    if (!nickname.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await createRoom(nickname.trim());
      saveAuth({
        roomCode: data.room_code,
        roomPlayerId: data.room_player_id,
        clientToken: data.client_token,
      });
      router.push(`/room/${data.room_code}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create room");
    } finally {
      setLoading(false);
    }
  }

  async function handleJoin() {
    if (!nickname.trim() || !joinCode.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await joinRoom(joinCode.trim().toUpperCase(), nickname.trim());
      saveAuth({
        roomCode: data.room_code,
        roomPlayerId: data.room_player_id,
        clientToken: data.client_token,
      });
      router.push(`/room/${data.room_code}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to join room");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-8 p-6">
      <div className="text-center">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-blue-400">Premier League</p>
        <h1 className="mt-2 text-4xl font-bold tracking-tight">Era Draft</h1>
        <p className="mt-3 text-slate-400">
          Spin for a club & era, draft your XI, and see who builds the best season record.
        </p>
      </div>

      <div className="card space-y-4 p-6">
        <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Your nickname</label>
        <input
          className="input"
          placeholder="Lucas"
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
        />

        <button className="btn-primary w-full py-3.5" disabled={loading || !nickname.trim()} onClick={handleCreate}>
          Create room
        </button>

        <div className="relative py-2 text-center text-xs text-slate-500">
          <span className="bg-slate-900 px-2">or join with code</span>
          <div className="absolute inset-x-0 top-1/2 -z-10 border-t border-slate-800" />
        </div>

        <input
          className="input font-mono tracking-widest"
          placeholder="ABCDE"
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && handleJoin()}
        />
        <button
          className="btn-secondary w-full"
          disabled={loading || !nickname.trim() || !joinCode.trim()}
          onClick={handleJoin}
        >
          Join room
        </button>

        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      <div className="card p-5 text-sm text-slate-400">
        <p className="font-semibold text-slate-200">How it works</p>
        <ol className="mt-3 space-y-2">
          <li className="flex gap-3">
            <span className="font-bold text-blue-400">1</span>
            <span>Pick your formation in the lobby</span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold text-blue-400">2</span>
            <span>
              <strong className="text-slate-300">Spin</strong> for a random club + five-year era
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold text-blue-400">3</span>
            <span>Draft one player into an open slot — repeat for 11 rounds</span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold text-blue-400">4</span>
            <span>Compare projected 38-game W-D-L records at the end</span>
          </li>
        </ol>
      </div>
    </main>
  );
}
