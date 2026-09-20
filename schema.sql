-- PyTodo Database Schema Evolution: Frictionless Pairing & Subtask Hierarchy

-- 1. Create accounts table for frictionless pairing
create table if not exists public.todo_accounts (
  pairing_code text primary key check (length(pairing_code) between 6 and 8),
  created_at timestamptz default timezone('utc'::text, now()) not null,
  last_active timestamptz default timezone('utc'::text, now()) not null
);

-- 2. Create tasks table partitioned by pairing code
create table if not exists public.todos (
  id text not null,
  pairing_code text not null references public.todo_accounts(pairing_code) on delete cascade,
  task_date date not null,
  title text not null,
  due_time text,
  duration_minutes integer,
  done boolean default false not null,
  subtasks jsonb default '[]'::jsonb not null,
  created_at timestamptz default timezone('utc'::text, now()) not null,
  updated_at timestamptz default timezone('utc'::text, now()) not null,
  deleted_at timestamptz,
  primary key (pairing_code, id)
);

create index if not exists idx_todos_pairing_date on public.todos(pairing_code, task_date);
create index if not exists idx_todos_pairing_updated on public.todos(pairing_code, updated_at);

-- 3. Create tombstones table for distributed deletion propagation (prevents zombie tasks)
create table if not exists public.todo_tombstones (
  id text not null,
  pairing_code text not null references public.todo_accounts(pairing_code) on delete cascade,
  deleted_at timestamptz default timezone('utc'::text, now()) not null,
  primary key (pairing_code, id)
);

create index if not exists idx_tombstones_pairing_deleted on public.todo_tombstones(pairing_code, deleted_at);

-- 4. Row Level Security ensuring tenant isolation
alter table public.todo_accounts enable row level security;
alter table public.todos enable row level security;
alter table public.todo_tombstones enable row level security;

-- Drop legacy permissive policies if they exist
drop policy if exists "Public account access by pairing key" on public.todo_accounts;
drop policy if exists "Public task access by pairing key" on public.todos;
drop policy if exists "Public tombstone access by pairing key" on public.todo_tombstones;

-- Strict tenant-isolated policies requiring pairing_code
create policy "Tenant isolation for todo_accounts"
  on public.todo_accounts for all
  using (pairing_code is not null and length(pairing_code) between 6 and 8)
  with check (pairing_code is not null and length(pairing_code) between 6 and 8);

create policy "Tenant isolation for todos"
  on public.todos for all
  using (pairing_code is not null and length(pairing_code) between 6 and 8)
  with check (pairing_code is not null and length(pairing_code) between 6 and 8);

create policy "Tenant isolation for tombstones"
  on public.todo_tombstones for all
  using (pairing_code is not null and length(pairing_code) between 6 and 8)
  with check (pairing_code is not null and length(pairing_code) between 6 and 8);

-- 5. Additive Columns: Discipline Streak, Themes, Retention, and Overdue History
alter table public.todo_accounts
  add column if not exists streak integer default 0 not null,
  add column if not exists highest_streak integer default 0 not null,
  add column if not exists last_evaluated_date date,
  add column if not exists theme text default 'classic' not null,
  add column if not exists retention_days integer default 3 not null,
  add column if not exists history jsonb default '{}'::jsonb not null;

alter table public.todos
  add column if not exists deleted_at timestamptz;
