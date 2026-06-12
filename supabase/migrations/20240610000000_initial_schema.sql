-- PL Era Draft — initial schema

create type room_status as enum (
  'lobby',
  'drafting',
  'simulating',
  'complete',
  'abandoned'
);

-- Dataset tables

create table if not exists clubs (
  id text primary key,
  name text not null,
  short_name text,
  slug text unique not null,
  is_active boolean default true,
  created_at timestamptz default now()
);

create table if not exists players (
  id text primary key,
  name text not null,
  slug text unique not null,
  primary_position text not null,
  secondary_positions text[] default '{}',
  base_rating int not null check (base_rating between 1 and 99),
  attack int check (attack between 0 and 99),
  midfield int check (midfield between 0 and 99),
  defence int check (defence between 0 and 99),
  goalkeeper int check (goalkeeper between 0 and 99),
  consistency int default 75 check (consistency between 1 and 99),
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists player_eras (
  id text primary key,
  player_id text not null references players(id),
  club_id text not null references clubs(id),
  era text not null,
  rating_modifier int not null default 0,
  include boolean not null default true,
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(player_id, club_id, era)
);

create table if not exists position_fits (
  id text primary key,
  player_id text not null references players(id),
  position text not null,
  fit int not null check (fit between 0 and 100),
  unique(player_id, position)
);

create table if not exists team_era_pools (
  id text primary key,
  club_id text not null references clubs(id),
  era text not null,
  spin_tier int not null check (spin_tier between 1 and 5),
  is_active boolean not null default true,
  min_eligible_players int default 5,
  created_at timestamptz default now(),
  unique(club_id, era)
);

create table if not exists formations (
  id text primary key,
  name text not null,
  slots jsonb not null,
  is_active boolean default true
);

-- Room tables

create table if not exists rooms (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  status room_status not null default 'lobby',
  host_room_player_id uuid,
  max_players int not null default 6,
  total_rounds int not null default 11,
  pick_timer_seconds int not null default 10,
  current_pick_index int not null default 0,
  current_spin_club_id text references clubs(id),
  current_spin_era text,
  current_pick_deadline timestamptz,
  draft_order uuid[] default '{}',
  settings jsonb not null default '{}',
  simulation_seed text,
  simulation_version text,
  draft_completed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists room_players (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references rooms(id) on delete cascade,
  nickname text not null,
  team_name text,
  formation_id text references formations(id),
  avatar_key text,
  client_token_hash text not null,
  draft_position int,
  is_host boolean default false,
  is_bot boolean default false,
  bot_difficulty text,
  normal_rerolls_left int not null default 1,
  late_lifelines_left int not null default 1,
  joined_at timestamptz default now(),
  last_seen_at timestamptz default now(),
  disconnected_at timestamptz,
  unique(room_id, nickname)
);

create table if not exists draft_picks (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references rooms(id) on delete cascade,
  room_player_id uuid not null references room_players(id) on delete cascade,
  pick_index int not null,
  round_index int not null,
  spin_club_id text not null references clubs(id),
  spin_era text not null,
  player_id text not null references players(id),
  slot_id text not null,
  player_era_id text references player_eras(id),
  draft_value int not null,
  was_auto_pick boolean not null default false,
  used_reroll boolean not null default false,
  picked_at timestamptz default now(),
  unique(room_id, pick_index),
  unique(room_id, player_id)
);

create table if not exists reroll_events (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references rooms(id) on delete cascade,
  room_player_id uuid not null references room_players(id) on delete cascade,
  pick_index int not null,
  old_club_id text references clubs(id),
  old_era text,
  new_club_id text references clubs(id),
  new_era text,
  reroll_type text not null,
  created_at timestamptz default now()
);

create table if not exists team_evaluations (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references rooms(id) on delete cascade,
  room_player_id uuid not null references room_players(id) on delete cascade,
  formation_id text not null references formations(id),
  internal_team_strength numeric,
  internal_attack_score numeric,
  internal_midfield_score numeric,
  internal_defence_score numeric,
  internal_gk_score numeric,
  internal_balance_score numeric,
  created_at timestamptz default now(),
  unique(room_id, room_player_id)
);

create table if not exists simulation_results (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references rooms(id) on delete cascade,
  room_player_id uuid not null references room_players(id) on delete cascade,
  internal_team_strength numeric not null,
  internal_season_strength numeric not null,
  internal_expected_points int not null,
  internal_points int not null,
  wins int not null,
  draws int not null,
  losses int not null,
  created_at timestamptz default now(),
  unique(room_id, room_player_id)
);

create index if not exists idx_player_eras_club_era on player_eras(club_id, era);
create index if not exists idx_draft_picks_room on draft_picks(room_id);
create index if not exists idx_room_players_room on room_players(room_id);
