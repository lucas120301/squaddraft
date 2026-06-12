import type { RoomState } from "@/stores/roomStore";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
const WS = process.env.NEXT_PUBLIC_WS_BASE_URL || "ws://localhost:8000/ws";

export type Auth = {
  roomCode: string;
  roomPlayerId: string;
  clientToken: string;
};

function authHeaders(auth: Auth) {
  return {
    "Content-Type": "application/json",
    "X-Room-Player-Id": auth.roomPlayerId,
    "X-Client-Token": auth.clientToken,
  };
}

async function parseError(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const body = JSON.parse(text) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch {
    /* not json */
  }
  return text || `Request failed (${response.status})`;
}

export async function createRoom(nickname: string) {
  const r = await fetch(`${API}/rooms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname }),
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json();
}

export async function joinRoom(code: string, nickname: string) {
  const r = await fetch(`${API}/rooms/${code}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname }),
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json();
}

export async function getRoom(code: string) {
  const r = await fetch(`${API}/rooms/${code}`, { cache: "no-store" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function updateLobby(auth: Auth, formationId: string, teamName?: string) {
  const r = await fetch(`${API}/rooms/${auth.roomCode}/lobby`, {
    method: "PUT",
    headers: authHeaders(auth),
    body: JSON.stringify({ formation_id: formationId, team_name: teamName }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function startDraft(auth: Auth) {
  const r = await fetch(`${API}/rooms/${auth.roomCode}/start`, {
    method: "POST",
    headers: authHeaders(auth),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function revealSpin(auth: Auth) {
  const r = await fetch(`${API}/rooms/${auth.roomCode}/draft/spin`, {
    method: "POST",
    headers: authHeaders(auth),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<RoomState>;
}

export async function makePick(auth: Auth, playerId: string, slotId: string) {
  const r = await fetch(`${API}/rooms/${auth.roomCode}/draft/pick`, {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ player_id: playerId, slot_id: slotId }),
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<RoomState>;
}

export async function reroll(auth: Auth) {
  const r = await fetch(`${API}/rooms/${auth.roomCode}/draft/reroll`, {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ reroll_type: "normal" }),
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<RoomState>;
}

export async function getFormations() {
  const r = await fetch(`${API}/formations`, { cache: "force-cache" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getClubs() {
  const r = await fetch(`${API}/clubs`, { cache: "force-cache" });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<{ clubs: { id: string; name: string; short_name: string }[] }>;
}

export function parseWsRoomState(msg: unknown): RoomState | null {
  if (!msg || typeof msg !== "object") return null;
  const m = msg as { type?: string; payload?: RoomState; room?: RoomState["room"] };
  if (m.payload?.room) return m.payload;
  if (m.room) return m as RoomState;
  return null;
}

export function connectWs(auth: Auth, onMessage: (data: unknown) => void) {
  const url = `${WS}/rooms/${auth.roomCode}?room_player_id=${auth.roomPlayerId}&client_token=${encodeURIComponent(auth.clientToken)}`;
  const ws = new WebSocket(url);
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data));
    } catch {
      /* ignore */
    }
  };
  return ws;
}

export async function getSlotFits(auth: Auth, playerId: string, slotIds: string[]) {
  const r = await fetch(
    `${API}/rooms/${auth.roomCode}/draft/fits?player_id=${playerId}&slot_ids=${slotIds.join(",")}`,
    { headers: authHeaders(auth) }
  );
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ fits: { slot_id: string; position: string; label: string; can_play: boolean }[] }>;
}

export function saveAuth(auth: Auth) {
  if (typeof window !== "undefined") {
    localStorage.setItem(`pl-draft-${auth.roomCode}`, JSON.stringify(auth));
  }
}

export function loadAuth(code: string): Auth | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(`pl-draft-${code}`);
  return raw ? JSON.parse(raw) : null;
}
