-- Era-specific positions (player role at club+era, not career-wide)

alter table player_eras
  add column if not exists primary_position text,
  add column if not exists secondary_positions text[] default '{}';
