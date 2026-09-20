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
  primary key (pairing_code, id)
);

create index if not exists idx_todos_pairing_date on public.todos(pairing_code, task_date);

-- 3. Row Level Security allowing anonymous access keyed by pairing code
alter table public.todo_accounts enable row level security;
alter table public.todos enable row level security;

create policy "Public account access by pairing key"
  on public.todo_accounts for all
  using (true) with check (true);

create policy "Public task access by pairing key"
  on public.todos for all
  using (true) with check (true);

-- 4. Additive Columns: Discipline Streak, Themes, Retention, and Overdue History
alter table public.todo_accounts
  add column if not exists streak integer default 0 not null,
  add column if not exists highest_streak integer default 0 not null,
  add column if not exists last_evaluated_date date,
  add column if not exists theme text default 'classic' not null,
  add column if not exists retention_days integer default 3 not null,
  add column if not exists history jsonb default '{}'::jsonb not null;