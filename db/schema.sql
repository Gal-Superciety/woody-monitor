-- Woody Clash Arena: minimal production-ready schema (PostgreSQL)

create extension if not exists "pgcrypto";

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint not null unique,
  wallet_address text unique,
  status text not null default 'active' check (status in ('active','flagged','banned')),
  created_at timestamptz not null default now(),
  last_active_at timestamptz
);

create table if not exists runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  started_at timestamptz not null,
  ended_at timestamptz not null,
  duration_ms integer not null check (duration_ms >= 0),
  score integer not null,
  perfect_hits integer not null default 0,
  good_hits integer not null default 0,
  misses integer not null default 0,
  max_combo integer not null default 0,
  modifier_id text,
  validation_status text not null default 'valid' check (validation_status in ('valid','suspect','rejected')),
  client_version text,
  input_fingerprint_hash text,
  created_at timestamptz not null default now()
);

create index if not exists idx_runs_user_created on runs(user_id, created_at desc);
create index if not exists idx_runs_validation on runs(validation_status);

create table if not exists match_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  opponent_user_id uuid references users(id),
  run_id uuid not null references runs(id),
  result text not null check (result in ('win','lose')),
  trophies_delta integer not null,
  elo_before integer not null,
  elo_after integer not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_match_results_user_created on match_results(user_id, created_at desc);

create table if not exists daily_leaderboard (
  leaderboard_date date not null,
  user_id uuid not null references users(id),
  best_score integer not null,
  rank integer not null,
  ap_bonus integer not null default 0,
  primary key (leaderboard_date, user_id)
);

create index if not exists idx_daily_leaderboard_rank on daily_leaderboard(leaderboard_date, rank asc);

create table if not exists weekly_points (
  week_id text not null,
  user_id uuid not null references users(id),
  arena_points integer not null default 0,
  capped_points integer not null default 0,
  placement_rank integer,
  placement_reward numeric(38, 0) not null default 0,
  pro_rata_reward numeric(38, 0) not null default 0,
  total_reward numeric(38, 0) not null default 0,
  primary key (week_id, user_id)
);

create index if not exists idx_weekly_points_rank on weekly_points(week_id, placement_rank);

create table if not exists claims (
  id uuid primary key default gen_random_uuid(),
  week_id text not null,
  user_id uuid not null references users(id),
  wallet_address text not null,
  amount numeric(38, 0) not null,
  merkle_leaf_hash text not null,
  claimed_onchain boolean not null default false,
  tx_hash text,
  claimed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (week_id, user_id)
);

create index if not exists idx_claims_week_wallet on claims(week_id, wallet_address);

create table if not exists economy_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  user_id uuid references users(id),
  amount numeric(38, 0) not null,
  token text not null default 'WOODY',
  ref_id text,
  created_at timestamptz not null default now()
);

create index if not exists idx_economy_events_type_created on economy_events(event_type, created_at desc);

create table if not exists risk_flags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  flag_type text not null,
  score numeric(10, 4) not null,
  status text not null default 'open' check (status in ('open','reviewed','closed')),
  context jsonb,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);

create index if not exists idx_risk_flags_user_status on risk_flags(user_id, status);

-- Utility view for weekly payout audits.
create or replace view v_weekly_payout_audit as
select
  wp.week_id,
  count(*) as users_count,
  sum(wp.arena_points) as total_raw_points,
  sum(wp.capped_points) as total_capped_points,
  sum(wp.total_reward) as total_reward
from weekly_points wp
group by wp.week_id;
