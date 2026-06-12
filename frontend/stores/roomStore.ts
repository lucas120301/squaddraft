import { create } from "zustand";

export type PlayerPick = {
  player_id: string;
  name: string;
  primary_position: string;
  slot_id: string;
  pick_index: number;
};

export type RoomPlayer = {
  id: string;
  nickname: string;
  team_name: string;
  formation_id: string | null;
  is_host: boolean;
  normal_rerolls_left: number;
  late_lifelines_left: number;
  picks: PlayerPick[];
};

export type RoomState = {
  room: {
    code: string;
    status: string;
    current_pick_index: number;
    timer_seconds_remaining: number | null;
    pick_timer_seconds: number;
    total_rounds: number;
    spin_revealed: boolean;
    spin_round: number | null;
    player_count: number | null;
  };
  players: RoomPlayer[];
  active_room_player_id: string | null;
  current_spin: { club_id: string; club_name: string; era: string } | null;
  available_players: {
    id: string;
    name: string;
    primary_position: string;
    secondary_positions: string[];
    positions_label?: string;
  }[];
  records: { team_name: string; nickname: string; record: string; wins: number; draws: number; losses: number }[];
  draft_order?: string[];
};

type Store = {
  state: RoomState | null;
  formations: { id: string; name: string; slots: { slot_id: string; position: string; x: number; y: number }[] }[];
  selectedPlayerId: string | null;
  setState: (s: RoomState) => void;
  setFormations: (f: Store["formations"]) => void;
  setSelectedPlayerId: (id: string | null) => void;
};

export const useRoomStore = create<Store>((set) => ({
  state: null,
  formations: [],
  selectedPlayerId: null,
  setState: (state) => set({ state }),
  setFormations: (formations) => set({ formations }),
  setSelectedPlayerId: (selectedPlayerId) => set({ selectedPlayerId }),
}));
