# PyTodo CLI — Product Specification & Feature Roadmap

> **Core Philosophy**: A high-urgency, ephemeral terminal to-do system designed to eliminate procrastination through loss aversion, daily accountability, and automated cross-device synchronization.

---

## Table of Contents
- [1. Product Vision & Psychological Mechanics](#1-product-vision--psychological-mechanics)
- [2. User-Requested Core Features](#2-user-requested-core-features)
  - [2.1 Ephemeral Daily Lifecycle (Midnight Wipe)](#21-ephemeral-daily-lifecycle-midnight-wipe)
  - [2.2 Task Deadlines & Target Durations](#22-task-deadlines--target-durations)
  - [2.3 Subtask Hierarchy](#23-subtask-hierarchy)
  - [2.4 In-Place Task & Subtask Editing](#24-in-place-task--subtask-editing)
  - [2.5 Frictionless 6–7 Digit Cross-Device Pairing](#25-frictionless-67-digit-cross-device-pairing)
  - [2.6 Offline-First Storage & Automatic Background Sync](#26-offline-first-storage--automatic-background-sync)
- [3. Suggested Extended Features](#3-suggested-extended-features)
  - [3.1 Accountability & Punishment Mechanics](#31-accountability--punishment-mechanics)
  - [3.2 Visual Urgency & Live Telemetry](#32-visual-urgency--live-telemetry)
  - [3.3 Focus, Discipline & Anti-Overload Constraints](#33-focus-discipline--anti-overload-constraints)
  - [3.4 Terminal Ergonomics & Sensory Feedback](#34-terminal-ergonomics--sensory-feedback)
- [4. Technical Architecture & Data Model](#4-technical-architecture--data-model)
- [5. Feature Approval & Decision Checklist](#5-feature-approval--decision-checklist)

---

## 1. Product Vision & Psychological Mechanics

Traditional to-do apps act as digital graveyards for forgotten intentions; tasks roll over indefinitely, removing any consequence for delay.

**PyTodo CLI** treats each day as a closed, high-stakes sprint:
1. **Urgency by Design**: Every task has an inescapable expiration horizon: **midnight of the current day** (system time).
2. **Punishment / Loss Aversion**: Incomplete tasks do not roll over silently. They are either wiped or logged in a permanent tally of failed commitments.
3. **Frictionless Terminal Interface**: Runs in any browser as an instant PWA powered by WebAssembly Python (Pyodide) and xterm.js.

---

## 2. User-Requested Core Features

### 2.1 Ephemeral Daily Lifecycle (Midnight Wipe)
* **Rule**: All tasks belong strictly to the current calendar date (`YYYY-MM-DD` in user's local system time).
* **Midnight Transition**:
  * On application boot and continuously via a background clock check, the system evaluates if the local calendar day has advanced.
  * If a date transition occurs, incomplete tasks from previous days are purged from the active view.
  * Optionally, failed tasks are recorded in an audit log (see [3.1](#31-accountability--punishment-mechanics)) before the active board resets to clean state for the new day.

### 2.2 Task Deadlines & Target Durations
* **Syntax Support**:
  * Absolute Deadline: `add "Write documentation" --due 18:30` (or `by 6pm`)
  * Estimated Duration: `add "Workout" --duration 45m`
* **Display in `ls`**:
  * Shows remaining time or exact deadline next to the task.
  * Dynamic color grading (e.g., green when plenty of time remains, switching to flashing red when deadline is imminent).

### 2.3 Subtask Hierarchy
* **Concept**: Any primary task can hold multiple subordinate checkpoints.
* **CLI Representation**:
  * Indented hierarchical tree under the parent in `ls`:
    ```text
    ID        STATUS   SYNC  TASK
    ---------------------------------------------
    b1c8e2    [TODO]    ✔    Prepare Quarterly Report [1/3 done]
      ├─ b1c8e2.1  [DONE]  ✔  Gather analytics data
      ├─ b1c8e2.2  [TODO]  ✔  Draft executive summary (Due 16:00)
      └─ b1c8e2.3  [TODO]  ✔  Slide deck export
    ```
* **Completion Mechanics**:
  * Marking a subtask done: `done b1c8e2.1`.
  * Marking the parent done: Prompts confirmation or automatically marks all subtasks complete.

### 2.4 In-Place Task & Subtask Editing
* **Command**: `edit <id> [options]`
* **Capabilities**:
  * Rename / change title: `edit b1c8e2 --title "New Title"`
  * Adjust or remove deadline: `edit b1c8e2 --due 20:00` or `edit b1c8e2 --clear-due`
  * Add a subtask: `edit b1c8e2 --add-sub "Review formatting"` (or dedicated `subtask add b1c8e2 "..."`)
  * Delete a subtask: `edit b1c8e2 --rm-sub 2` (or `subtask rm b1c8e2.2`)

### 2.5 Frictionless 6–7 Digit Cross-Device Pairing
* **Eliminating Email/Password Friction**:
  * Users do not need an email or password to sync across devices.
  * A user can generate a cryptographically random, collision-resistant **6 or 7-digit code** (e.g., `link generate` -> `Your Key: 849201`).
  * On a second device (phone, laptop, tablet), running `link 849201` instantly connects to that dataset.
* **Persistence**:
  * The link key is saved in `localStorage`.
  * Multi-tenant data isolation in Supabase is keyed to the pairing code.

### 2.6 Offline-First Storage & Automatic Background Sync
* **Zero Latency (Optimistic UI)**:
  * Commands write instantly to browser `localStorage` (0ms delay). The terminal never pauses waiting for network responses.
  * Mutated records are marked with `synced: false`.
* **Automatic Background Synchronization**:
  * **On Mutation**: Immediately triggers a debounced asynchronous push to Supabase in the background.
  * **On Reconnect**: Binds to `window.addEventListener('online')` to immediately flush pending sync queues when network connectivity is restored.
  * **Periodic Pull (Heartbeat)**: Periodically checks for changes made by other linked devices every 30–60 seconds.
  * **Conflict Resolution**: Last-Write-Wins (LWW) resolution based on UTC ISO-8601 timestamps (`updated_at`).
* **Status Badges**:
  * Prompt / header reflects connection status:
    * `[● SYNCED]` (All data backed up)
    * `[◐ SYNCING]` (Uploading / merging changes)
    * `[○ OFFLINE]` (Working locally; changes queued safely)

---

## 3. Suggested Extended Features

### 3.1 Accountability & Punishment Mechanics
* **The "Hall of Shame" / Graveyard (`shame` or `graveyard`)**:
  * When midnight wipes uncompleted tasks, they are moved to a graveyard ledger.
  * Running `shame` outputs an ASCII tombstone with the historical count and list of abandoned tasks, keeping past failures visible.
* **The Discipline Streak (`streak`)**:
  * Tracks consecutive days where 100% of tasks were completed before midnight.
  * If even one active task expires at midnight, the streak abruptly resets to 0 with a stark terminal alert.
* **"Admit Defeat" Penalty on Deletion (`giveup <id>`)**:
  * Users cannot quietly delete difficult tasks.
  * Attempting `rm <id>` requires using `giveup <id>` or typing a confirmation phrase (e.g., "I quit").
* **Emergency Mercy Token (`mercy <id>`)**:
  * Real-world emergencies happen. A user is allocated exactly **one** Mercy Token every 7 days.
  * Lets the user carry over a single task past midnight without breaking their streak.

### 3.2 Visual Urgency & Live Telemetry
* **Live Ticking Header / Prompt**:
  * Live countdown directly in the terminal prompt or banner:
    ```text
    [TODAY REMAINING: 03h 42m 15s] [TASKS: 3/5 DONE] [● SYNCED]
    todo>
    ```
* **Visual Task Aging (Color Heatmap in `ls`)**:
  * Normal (> 4 hours remaining): Calm Cyan / Green
  * Warning (< 2 hours remaining): Amber / Yellow `[DUE SOON]`
  * Critical (< 45 mins remaining): Blinking Bold Red `[URGENT: 32m LEFT]`
* **Live Dashboard Monitor (`top` or `watch`)**:
  * Fullscreen auto-updating dashboard (like Linux `htop`) displaying:
    * Day progress bar: `[====================>..........] 68% of Day Gone`
    * Completion progress bar: `[==========>....................] 33% Completed`
    * Real-time countdowns for all active tasks.

### 3.3 Focus, Discipline & Anti-Overload Constraints
* **The "Ivy Lee" Overcommitment Cap (Max 5–7 Tasks/Day)**:
  * Psychological limit: adding more than 6 tasks triggers a warning:
    `[!] OVERCOMMITMENT BLOCKED: Finish an existing task before adding more.`
* **Terminal Focus / Pomodoro Mode (`focus <id> [minutes]`)**:
  * Launches an interactive single-task focus screen with a ticking ASCII progress bar and an audio chime upon completion.

### 3.4 Terminal Ergonomics & Sensory Feedback
* **8-Bit Terminal Audio FX (Native Web Audio API)**:
  * Zero external audio files required (generated via oscillator waveforms).
  * Completion sound: Upbeat retro 8-bit arcade chime on `done`.
  * Midnight wipe sound: Low descending 8-bit buzzer.
  * Can be toggled on/off with `sound on/off`.
* **Command History & Tab Autocompletion**:
  * `Up` and `Down` arrow keys cycle through command history.
  * `Tab` key auto-completes task IDs and subtask IDs.

---

## 4. Technical Architecture & Data Model

### 4.1 Task Entity Schema
```json
{
  "id": "b1c8e2",
  "title": "Prepare Quarterly Report",
  "content": "Include revenue, churn, and team projections",
  "date": "2026-09-17",
  "due_time": "18:00",
  "duration_minutes": 90,
  "done": false,
  "created_at": "2026-09-17T12:00:00.000Z",
  "updated_at": "2026-09-17T12:30:00.000Z",
  "synced": true,
  "subtasks": [
    {
      "id": "b1c8e2.1",
      "title": "Gather analytics data",
      "done": true,
      "updated_at": "2026-09-17T12:15:00.000Z"
    },
    {
      "id": "b1c8e2.2",
      "title": "Draft executive summary",
      "done": false,
      "updated_at": "2026-09-17T12:30:00.000Z"
    }
  ]
}
```

### 4.2 Database Schema (`schema.sql` Evolution)
```sql
create table if not exists public.todo_accounts (
  pairing_code text primary key,
  streak integer default 0,
  last_active_date date default current_date,
  created_at timestamptz default timezone('utc'::text, now())
);

create table if not exists public.todos (
  id text primary key,
  pairing_code text not null references public.todo_accounts(pairing_code) on delete cascade,
  task_date date not null,
  title text not null,
  content text default '',
  due_time text,
  duration_minutes integer,
  done boolean default false,
  subtasks jsonb default '[]'::jsonb,
  updated_at timestamptz default timezone('utc'::text, now()) not null
);

create table if not exists public.graveyard (
  id text primary key,
  pairing_code text not null references public.todo_accounts(pairing_code) on delete cascade,
  task_date date not null,
  title text not null,
  subtasks jsonb default '[]'::jsonb,
  failed_at timestamptz default timezone('utc'::text, now()) not null
);
```

---

## 5. Feature Approval & Decision Checklist

Use this checklist to decide which items to include in the implementation plan:

### User-Requested Core Features
- [x] **Midnight Wipe**: Incomplete tasks automatically expire and clear at 00:00 system time.
- [x] **Due Time & Duration**: Optional `--due HH:MM` and `--duration Xm` flags with color alerts.
- [x] **Subtask Trees**: Support nested subtasks with progress counters (`[X/Y done]`).
- [x] **Task Editing**: Modify task name, due time, description, and manage subtasks via `edit`.
- [x] **6–7 Digit Key Device Sync**: Connect devices instantly using a 6 or 7-digit code without passwords.
- [x] **Offline-First Auto-Sync**: 0ms local storage writes, auto-syncing in background on reconnect.

### Suggested Features for Confirmation
- [ ] **Hall of Shame / Graveyard (`shame`)**: Log expired tasks permanently instead of deleting silently.
- [ ] **Discipline Streak (`streak`)**: Track consecutive 100% days; reset to 0 on failure.
- [ ] **Giveup Penalty (`giveup <id>`)**: Require explicit abandonment admission to drop a task.
- [ ] **Emergency Mercy Token (`mercy <id>`)**: 1 token per week to rescue a task from midnight wipe.
- [x] **Live Prompt Countdown**: Ticking countdown to midnight visible in the terminal prompt.
- [x] **Visual Task Heatmap in `ls`**: Dynamic color shift as deadlines approach.
- [x] **Live HTOP Dashboard (`top`)**: Fullscreen live-updating progress monitor.
- [x] **8-Bit Retro Audio FX**: Web Audio synthesizer chimes for completions and fails.
- [ ] **Overcommitment Cap (Max 6 Tasks)**: Block adding excessive tasks in one day.
- [x] **Shell Up/Down History & Tab Completion**: Terminal navigation ergonomics.

---
*(Edit or annotate this file directly, and let me know when you are ready to proceed with implementation!)*
