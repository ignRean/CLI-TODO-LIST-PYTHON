import json
import uuid
import shlex
import inspect
import re
import math
import unicodedata
from datetime import datetime, timezone, timedelta
try:
    from js import window, supabaseClient
except ImportError:
    window = None
    supabaseClient = None

STORAGE_KEY = "py_pwa_todos"
PAIRING_STORAGE_KEY = "py_todo_pairing_code"
HISTORY_STORAGE_KEY = "py_todo_history"
STREAK_STORAGE_KEY = "py_todo_streak"
RETENTION_STORAGE_KEY = "py_todo_retention_days"
THEME_STORAGE_KEY = "py_todo_theme"
TOMBSTONES_STORAGE_KEY = "py_todo_tombstones"

# ANSI Color & Formatting Constants
C_RESET       = "\x1b[0m"
C_BOLD        = "\x1b[1m"
C_DIM         = "\x1b[2m"
C_ITALIC      = "\x1b[3m"
C_UNDERLINE   = "\x1b[4m"
C_BLINK       = "\x1b[5m"
C_INVERT      = "\x1b[7m"

C_RED         = "\x1b[31m"
C_GREEN       = "\x1b[32m"
C_YELLOW      = "\x1b[33m"
C_BLUE        = "\x1b[34m"
C_MAGENTA     = "\x1b[35m"
C_CYAN        = "\x1b[36m"
C_WHITE       = "\x1b[37m"
C_GRAY        = "\x1b[90m"
C_AMBER       = "\x1b[33m"

# Bright / High-Intensity ANSI Colors
C_B_RED       = "\x1b[1;31m"
C_B_GREEN     = "\x1b[1;32m"
C_B_YELLOW    = "\x1b[1;33m"
C_B_CYAN      = "\x1b[1;36m"
C_B_WHITE     = "\x1b[1;37m"
C_ORANGE      = "\x1b[38;5;208m"
C_B_BLINK_RED = "\x1b[1;5;31m"
C_INV_RED     = "\x1b[1;7;31m"

# 1. Sanitization & Visual Cell Alignment
ANSI_ESCAPE_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])|[\x00-\x08\x0b-\x1f\x7f-\x9f]')

def sanitize_text(text: str) -> str:
    """Strips terminal escape sequences and non-printable control characters."""
    if not text:
        return ""
    return ANSI_ESCAPE_RE.sub('', str(text)).strip()

def is_wide_or_emoji(c: str) -> bool:
    cp = ord(c)
    if unicodedata.east_asian_width(c) in ('W', 'F'):
        return True
    if (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or (0x1F1E6 <= cp <= 0x1F1FF):
        return True
    return False

def get_visual_width(s: str) -> int:
    """Calculates visible terminal cell width, accounting for wide East-Asian characters & emojis."""
    clean = ANSI_ESCAPE_RE.sub('', s)
    width = 0
    for c in clean:
        cp = ord(c)
        if cp in (0x200D, 0xFE0E, 0xFE0F) or (0xE0100 <= cp <= 0xE01EF):
            continue
        width += 2 if is_wide_or_emoji(c) else 1
    return width

def truncate_visual(s: str, max_cells: int, suffix: str = "…") -> str:
    """Safely truncates raw string to max visual cells, appending suffix if truncated."""
    if max_cells <= 0:
        return ""
    clean = ANSI_ESCAPE_RE.sub('', s)
    if get_visual_width(clean) <= max_cells:
        return clean
    
    suffix_w = get_visual_width(suffix)
    target = max(1, max_cells - suffix_w)
    accum = []
    curr_w = 0
    for c in clean:
        cp = ord(c)
        if cp in (0x200D, 0xFE0E, 0xFE0F) or (0xE0100 <= cp <= 0xE01EF):
            accum.append(c)
            continue
        w = 2 if is_wide_or_emoji(c) else 1
        if curr_w + w > target:
            break
        accum.append(c)
        curr_w += w
    return "".join(accum) + suffix

def get_terminal_width() -> int:
    """Returns the current terminal column width via JS bridge with robust fallbacks."""
    try:
        cols = int(window.PyTodoBridge.getTerminalCols())
        if cols > 20:
            return cols
    except Exception:
        pass
    try:
        if hasattr(window, "term") and window.term.cols:
            return int(window.term.cols)
    except Exception:
        pass
    return 80

def pad_string(s: str, target_width: int, align: str = "left") -> str:
    """Pads a string to target terminal cell width, taking wide characters into account."""
    current_width = get_visual_width(s)
    pad_needed = max(0, target_width - current_width)
    if align == "right":
        return (" " * pad_needed) + s
    return s + (" " * pad_needed)

# 2. Local Time & Date Utilities
def get_local_now():
    """Returns local wall-clock datetime using JS date interop for accuracy across timezones."""
    try:
        now_ms = int(window.Date.now())
        offset_min = int(window.Date.new().getTimezoneOffset())
        utc_dt = datetime.fromtimestamp(now_ms / 1000.0, timezone.utc)
        local_dt = (utc_dt - timedelta(minutes=offset_min)).replace(tzinfo=None)
        return local_dt
    except Exception:
        return datetime.now()

def get_local_date_str() -> str:
    """Returns current local calendar date string 'YYYY-MM-DD'."""
    try:
        raw_date = str(window.PyTodoBridge.getLocalISODate())
        if raw_date and len(raw_date) == 10:
            return raw_date
    except Exception:
        pass
    return get_local_now().strftime("%Y-%m-%d")

# 3. Storage Utilities & Ephemeral Midnight Rollover
def get_pairing_code():
    try:
        val = window.localStorage.getItem(PAIRING_STORAGE_KEY)
        return str(val).strip() if val else None
    except Exception:
        return None

def set_pairing_code(code: str):
    try:
        if code:
            window.localStorage.setItem(PAIRING_STORAGE_KEY, str(code).strip())
        else:
            window.localStorage.removeItem(PAIRING_STORAGE_KEY)
    except Exception:
        pass

def normalize_and_migrate_todos(todos):
    """
    Guarantees that every task has:
    1. A persistent backend uuid for Supabase synchronization.
    2. A clean, human-friendly sequential display ID ('1', '2', '3'...).
    3. Dot-notation subtask IDs ('1.1', '1.2'...).
    Automatically migrates legacy hex UUIDs from previous versions.
    """
    if not isinstance(todos, list):
        return []
    changed = False
    used_ids = set()
    next_id = 1

    todos = [t for t in todos if isinstance(t, dict)]
    for t in todos:
        if not t.get("uuid"):
            t["uuid"] = str(t.get("id") or uuid.uuid4())
            changed = True

        cur_id = str(t.get("id", "")).strip()
        if not cur_id.isdigit() or int(cur_id) <= 0 or cur_id in used_ids:
            while str(next_id) in used_ids:
                next_id += 1
            t["id"] = str(next_id)
            used_ids.add(t["id"])
            next_id += 1
            changed = True
        else:
            used_ids.add(cur_id)
            if int(cur_id) >= next_id:
                next_id = int(cur_id) + 1

        parent_id = t["id"]
        subtasks = t.get("subtasks", [])
        if isinstance(subtasks, list):
            valid_subs = [s for s in subtasks if isinstance(s, dict)]
            if len(valid_subs) != len(subtasks):
                t["subtasks"] = valid_subs
                subtasks = valid_subs
                changed = True
            for idx, s in enumerate(subtasks):
                cur_sub_id = str(s.get("id", "")).strip()
                if not cur_sub_id or not cur_sub_id.startswith(f"{parent_id}."):
                    s["id"] = f"{parent_id}.{idx + 1}"
                    changed = True
                if not s.get("uuid"):
                    s["uuid"] = str(uuid.uuid4())
                    changed = True

    if changed:
        try:
            window.localStorage.setItem(STORAGE_KEY, json.dumps(todos))
        except Exception:
            pass
    return todos

def get_local_todos():
    try:
        raw = window.localStorage.getItem(STORAGE_KEY)
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return normalize_and_migrate_todos(data)
        return []
    except Exception:
        return []

def save_local_todos(todos):
    try:
        window.localStorage.setItem(STORAGE_KEY, json.dumps(todos))
    except Exception as err:
        pass

def get_tombstones() -> list:
    try:
        raw = window.localStorage.getItem(TOMBSTONES_STORAGE_KEY)
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    except Exception:
        return []

def save_tombstones(tombstones: list):
    try:
        # Keep unique, bounded to last 500 records
        cleaned = list(dict.fromkeys(str(x) for x in tombstones))[-500:]
        window.localStorage.setItem(TOMBSTONES_STORAGE_KEY, json.dumps(cleaned))
    except Exception:
        pass

def add_tombstone(task_uuid: str):
    if not task_uuid:
        return
    current = get_tombstones()
    if task_uuid not in current:
        current.append(str(task_uuid))
        save_tombstones(current)


def get_retention_days() -> int:
    """Returns configured retention days for overdue tasks (1 to 7, default 3)."""
    try:
        val = window.PyTodoBridge.getRetentionDays()
        d = int(val)
        if 1 <= d <= 7:
            return d
    except Exception:
        pass
    try:
        val = window.localStorage.getItem(RETENTION_STORAGE_KEY)
        if val:
            d = int(val)
            if 1 <= d <= 7:
                return d
    except Exception:
        pass
    return 3

def set_retention_days(days: int) -> bool:
    """Sets retention days for overdue tasks (clamped to 1..7)."""
    days = max(1, min(7, int(days)))
    try:
        window.PyTodoBridge.setRetentionDays(days)
    except Exception:
        try:
            window.localStorage.setItem(RETENTION_STORAGE_KEY, str(days))
        except Exception:
            pass
    return True

def get_history_todos() -> dict:
    """Returns the overdue history dictionary: { 'YYYY-MM-DD': [task_dict, ...] }."""
    try:
        raw = window.localStorage.getItem(HISTORY_STORAGE_KEY)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}

def save_history_todos(history: dict):
    """Persists the overdue history dictionary."""
    try:
        window.localStorage.setItem(HISTORY_STORAGE_KEY, json.dumps(history))
    except Exception:
        pass

def get_streak_data() -> dict:
    """Returns discipline streak state dictionary."""
    default_data = {
        "current_streak": 0,
        "highest_streak": 0,
        "last_evaluated_date": "",
        "history_log": {}
    }
    try:
        raw = window.localStorage.getItem(STREAK_STORAGE_KEY)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v
                return data
    except Exception:
        pass
    return default_data

def save_streak_data(data: dict):
    """Persists discipline streak state dictionary."""
    try:
        window.localStorage.setItem(STREAK_STORAGE_KEY, json.dumps(data))
    except Exception:
        pass

def prune_history_retention(history: dict, retention_days: int, today_str: str):
    """Prunes history dates strictly older than (today - retention_days)."""
    try:
        today_dt = datetime.strptime(today_str, "%Y-%m-%d").date()
    except Exception:
        today_dt = get_local_now().date()
    cutoff_date = (today_dt - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    pruned_count = 0
    cleaned = {}
    for d, tasks in history.items():
        if d >= cutoff_date:
            cleaned[d] = tasks
        else:
            pruned_count += len(tasks)
    return (cleaned, pruned_count)

def enforce_day_rollover() -> int:
    """
    Synchronous Day Transition & Rollover Engine:
    1. Extracts uncompleted tasks from past calendar days into History Graveyard.
    2. Evaluates consecutive discipline streak:
       - If yesterday (or past active days) had tasks and 100% were completed before midnight -> streak increments.
       - If any incomplete tasks remained -> streak resets to 0.
       - If user had multi-day inactivity gap -> streak resets to 0.
    3. Prunes history older than retention_days (default 3, max 7).
    4. Keeps today's active tasks clean.
    """
    todos = get_local_todos()
    today = get_local_date_str()
    history = get_history_todos()
    streak_data = get_streak_data()
    retention_days = get_retention_days()

    past_tasks = []
    active_todos = []
    for t in todos:
        t_date = t.get("task_date") or t.get("date") or today
        if t_date < today:
            past_tasks.append(t)
        else:
            active_todos.append(t)

    wiped_count = 0
    past_by_date = {}
    for t in past_tasks:
        t_date = t.get("task_date") or t.get("date")
        if not t_date:
            continue
        if t_date not in past_by_date:
            past_by_date[t_date] = []
        past_by_date[t_date].append(t)

    for d, d_tasks in past_by_date.items():
        if d not in history:
            history[d] = []
        existing_ids = {t["id"] for t in history[d] if isinstance(t, dict)}
        for p in d_tasks:
            if not p.get("done", False):
                if p["id"] not in existing_ids:
                    history[d].append(p)
                    wiped_count += 1

    # Streak state machine
    last_eval = streak_data.get("last_evaluated_date")
    try:
        today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    except Exception:
        today_dt = get_local_now().date()

    yesterday_dt = today_dt - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%d")

    if last_eval != yesterday_str and last_eval != today:
        if last_eval:
            try:
                last_dt = datetime.strptime(last_eval, "%Y-%m-%d").date()
                day_gap = (yesterday_dt - last_dt).days
            except Exception:
                day_gap = 1
        else:
            day_gap = 1

        if day_gap > 1:
            streak_data["current_streak"] = 0
        elif day_gap == 1:
            y_tasks = past_by_date.get(yesterday_str, [])
            if y_tasks:
                y_total = len(y_tasks)
                y_done = sum(1 for t in y_tasks if t.get("done", False))
                if y_done == y_total and y_total > 0:
                    streak_data["current_streak"] += 1
                    streak_data["highest_streak"] = max(streak_data["highest_streak"], streak_data["current_streak"])
                    streak_data["history_log"][yesterday_str] = {"total": y_total, "done": y_done, "success": True}
                    try:
                        window.PyTodoBridge.playSound("streak")
                    except Exception:
                        pass
                else:
                    streak_data["current_streak"] = 0
                    streak_data["history_log"][yesterday_str] = {"total": y_total, "done": y_done, "success": False}
            else:
                streak_data["current_streak"] = 0

        streak_data["last_evaluated_date"] = yesterday_str

    history, _ = prune_history_retention(history, retention_days, today)

    if wiped_count > 0 or len(active_todos) != len(todos):
        save_local_todos(active_todos)
        save_history_todos(history)
        save_streak_data(streak_data)
        if wiped_count > 0:
            try:
                window.PyTodoBridge.playSound("wipe")
            except Exception:
                pass
    else:
        save_history_todos(history)
        save_streak_data(streak_data)

    return wiped_count

def purge_expired_tasks():
    return enforce_day_rollover()

# 4. Deadline, Duration & Heatmap Formatter
def parse_duration_seconds(val: str) -> int | None:
    """
    Parses flexible duration inputs into exact integer seconds.
    Supports:
      - Compound: '1h30m', '1h 30m 15s', '25m 30s'
      - Fractional: '1.5h' (5400s), '0.5h' (1800s), '2.5m' (150s)
      - Plain seconds: '30s', '90s'
      - Plain numbers: '25' -> 25 minutes (1500s)
    Rejects:
      - Negative values ('-10m')
      - Non-positive totals (0s)
      - Floating-point overflow / infinity / NaN
      - Unrecognized formats
    """
    if not val:
        return None
    val = str(val).strip().lower()
    
    # Reject explicit negatives and non-finite floats
    if "-" in val or "inf" in val or "nan" in val:
        return None

    # Plain integer or float (default to minutes)
    try:
        n = float(val)
        if math.isinf(n) or math.isnan(n):
            return None
        # Clamp to reasonable bounds: maximum 1440 minutes (24 hours)
        if 0 < n <= 1440:
            return int(round(n * 60))
        return None
    except ValueError:
        pass

    # Normalize whitespace
    clean = val.replace(" ", "")
    
    # Regex matching optional float hours, optional float minutes, optional float seconds
    pattern = r'^(?:([0-9]+(?:\.[0-9]+)?)h)?(?:([0-9]+(?:\.[0-9]+)?)m)?(?:([0-9]+(?:\.[0-9]+)?)s)?$'
    match = re.match(pattern, clean)
    if match and (match.group(1) or match.group(2) or match.group(3)):
        try:
            h = float(match.group(1)) if match.group(1) else 0.0
            m = float(match.group(2)) if match.group(2) else 0.0
            s = float(match.group(3)) if match.group(3) else 0.0
            if any(math.isinf(x) or math.isnan(x) for x in (h, m, s)):
                return None
            total_sec = int(round(h * 3600 + m * 60 + s))
            if total_sec > 0:
                return total_sec
            return None
        except Exception:
            return None

    return None

def parse_duration(val: str) -> int | None:
    """Parses duration string into total minutes. Backward-compatible with existing commands."""
    sec = parse_duration_seconds(val)
    if sec is None:
        return None
    return max(1, int(round(sec / 60)))

def parse_due_input(val_str: str, now: datetime = None):
    """
    Parses complex due inputs into (date_str, time_str).
    Supports:
    - Special keywords: 'midnight' (23:59), 'noon' (12:00)
    - Relative offsets: 'in 2h', 'in 30m', 'in 1.5 hours', 'in 45 mins'
    - Times: '18:00', '6pm', '6:00pm', '6:00 pm', '6 pm', '9:30am'
    - Dates: 'tomorrow', 'today', '2026-09-19'
    - Combinations: 'tomorrow 6pm', '2026-09-19 18:00', 'today 18:30'
    """
    if not val_str:
        return (None, None)
    if now is None:
        now = get_local_now()

    val = str(val_str).strip().lower()
    res_date = None
    res_time = None

    # Date parsing
    if "tomorrow" in val:
        res_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "today" in val:
        res_date = now.strftime("%Y-%m-%d")
    else:
        dm = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', val)
        if dm:
            res_date = dm.group(1)

    # Relative offset parsing: 'in 2h', 'in 30m', 'in 1.5h', 'in 45 mins'
    rel_m = re.search(r'\bin\s+([0-9]+(?:\.[0-9]+)?)\s*(h|hr|hrs|hours?|m|min|mins|minutes?)\b', val)
    if rel_m:
        try:
            amt = float(rel_m.group(1))
            unit = rel_m.group(2)
            if not math.isinf(amt) and not math.isnan(amt) and amt > 0:
                if unit.startswith("h"):
                    target_dt = now + timedelta(hours=amt)
                else:
                    target_dt = now + timedelta(minutes=amt)
                if not res_date:
                    res_date = target_dt.strftime("%Y-%m-%d")
                res_time = target_dt.strftime("%H:%M")
                return (res_date, res_time)
        except Exception:
            pass

    # Keyword times: 'midnight' -> 23:59, 'noon' -> 12:00
    if "midnight" in val:
        res_time = "23:59"
    elif "noon" in val:
        res_time = "12:00"
    else:
        # Time parsing: 12h format (e.g. 6pm, 6:00pm, 6:00 pm, 6 pm)
        # Note: negative lookbehind ensures no leading negative sign or word char (e.g. rejects -6pm)
        m12 = re.search(r'(?<![-\w])([1-9]|1[0-2])(?::([0-5]\d))?\s*(am|pm)\b', val)
        if m12:
            h = int(m12.group(1))
            m = int(m12.group(2)) if m12.group(2) else 0
            p = m12.group(3)
            if p == "pm" and h != 12:
                h += 12
            elif p == "am" and h == 12:
                h = 0
            res_time = f"{h:02d}:{m:02d}"
        else:
            # 24h format (e.g. 18:00, 09:30, 23:45)
            # Rejects negative values like -18:00 and ignores if followed by am/pm (like 0:00pm)
            m24 = re.search(r'(?<![-\w])([01]?\d|2[0-3]):([0-5]\d)(?!\s*(?:am|pm|[a-zA-Z]))\b', val)
            if m24:
                h = int(m24.group(1))
                m = int(m24.group(2))
                res_time = f"{h:02d}:{m:02d}"

    return (res_date, res_time)

def parse_due_time(val: str):
    """Normalizes due time strings ('18:30', '6pm', '6:00 pm', '4:15pm') to 24-hour 'HH:MM'."""
    _, t = parse_due_input(val)
    return t

# 4.1 Natural Language Task & Subtask Parser Engine
_DURATION_REGEX = re.compile(
    r'\b(?:for|duration|dur)\s+([0-9]+(?:\.[0-9]+)?\s*(?:h|hr|hrs|hours?|m|min|mins|minutes?|s|sec|seconds?)(?:\s*(?:and\s*)?[0-9]+(?:\.[0-9]+)?\s*(?:m|min|mins|minutes?|s|sec|seconds?))?)\b',
    re.IGNORECASE
)

_PREP_DUE_REGEX = re.compile(
    r'\b(?:by|due|before)\s+('
    r'(?:today|tomorrow|\d{4}-\d{2}-\d{2})(?:\s+(?:at\s+)?(?:[01]?\d|2[0-3]):[0-5]\d|\s+(?:at\s+)?(?:[1-9]|1[0-2])(?::[0-5]\d)?\s*(?:am|pm)|midnight|noon)?'
    r'|(?:[01]?\d|2[0-3]):[0-5]\d(?!\s*(?:am|pm|[a-zA-Z]))'
    r'|(?:[1-9]|1[0-2])(?::[0-5]\d)?\s*(?:am|pm)'
    r'|midnight|noon'
    r')\b'
    r'|'
    r'\bat\s+('
    r'(?:[01]?\d|2[0-3]):[0-5]\d(?!\s*(?:am|pm|[a-zA-Z]))'
    r'|(?:[1-9]|1[0-2])(?::[0-5]\d)?\s*(?:am|pm)'
    r'|midnight|noon'
    r')\b'
    r'|'
    r'\b(in\s+[0-9]+(?:\.[0-9]+)?\s*(?:h|hr|hrs|hours?|m|min|mins|minutes?))\b',
    re.IGNORECASE
)

_TRAILING_DUE_REGEX = re.compile(
    r'\s+('
    r'(?:today|tomorrow|\d{4}-\d{2}-\d{2})(?:\s+(?:at\s+)?(?:[01]?\d|2[0-3]):[0-5]\d|\s+(?:at\s+)?(?:[1-9]|1[0-2])(?::[0-5]\d)?\s*(?:am|pm)|midnight|noon)?'
    r'|(?:at\s+|@\s+)?(?:[01]?\d|2[0-3]):[0-5]\d(?!\s*(?:am|pm|[a-zA-Z]))'
    r'|(?:at\s+|@\s+)?(?:[1-9]|1[0-2])(?::[0-5]\d)?\s*(?:am|pm)'
    r'|in\s+[0-9]+(?:\.[0-9]+)?\s*(?:h|hr|hrs|hours?|m|min|mins|minutes?)'
    r'|midnight|noon'
    r')([.!?])?$',
    re.IGNORECASE
)

def normalize_duration_str(raw_dur: str) -> str:
    s = raw_dur.lower()
    s = re.sub(r'\band\b', ' ', s)
    s = re.sub(r'\bhours?\b|\bhrs?\b', 'h', s)
    s = re.sub(r'\bminutes?\b|\bmins?\b', 'm', s)
    s = re.sub(r'\bseconds?\b|\bsecs?\b', 's', s)
    s = re.sub(r'\s+', '', s)
    return s

def parse_natural_task(
    raw_title: str,
    explicit_due: str | None = None,
    explicit_duration: int | None = None,
    now: datetime | None = None
) -> dict:
    if now is None:
        now = get_local_now()

    working_title = raw_title.strip()
    extracted_date = None
    extracted_time = None
    extracted_duration = None

    # 1. Duration extraction (if not explicitly overridden by --duration)
    if explicit_duration is None:
        dur_match = _DURATION_REGEX.search(working_title)
        if dur_match:
            raw_dur_str = dur_match.group(1)
            norm_dur = normalize_duration_str(raw_dur_str)
            parsed_dur = parse_duration(norm_dur)
            if parsed_dur is not None:
                extracted_duration = parsed_dur
                match_end = dur_match.end()
                trailing_p = ""
                if match_end < len(working_title) and working_title[match_end] in ".!?":
                    trailing_p = working_title[match_end]
                    match_end += 1
                working_title = (working_title[:dur_match.start()] + trailing_p + " " + working_title[match_end:]).strip()

    # 2. Due extraction (if not explicitly overridden by --due)
    if explicit_due is None:
        while True:
            due_match = _PREP_DUE_REGEX.search(working_title)
            if due_match:
                candidate = next(g for g in due_match.groups() if g is not None).strip()
                p_date, p_time = parse_due_input(candidate, now=now)
                if p_date or p_time:
                    if p_date:
                        extracted_date = p_date
                    if p_time:
                        extracted_time = p_time
                    match_end = due_match.end()
                    trailing_p = ""
                    if match_end < len(working_title) and working_title[match_end] in ".!?":
                        trailing_p = working_title[match_end]
                        match_end += 1
                    working_title = (working_title[:due_match.start()] + trailing_p + " " + working_title[match_end:]).strip()
                    continue
            break

        if not extracted_time and not extracted_date:
            trail_match = _TRAILING_DUE_REGEX.search(working_title)
            if trail_match:
                candidate = trail_match.group(1).strip()
                punc = trail_match.group(2) or ""
                p_date, p_time = parse_due_input(candidate, now=now)
                if p_date or p_time:
                    extracted_date = p_date
                    extracted_time = p_time
                    working_title = working_title[:trail_match.start()].strip() + punc

    # Clean parentheses left empty e.g. "()" or "( )"
    clean_title = re.sub(r'\(\s*\)', '', working_title)
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    clean_title = re.sub(r'\s+([.!?,])', r'\1', clean_title)

    if not clean_title and raw_title.strip():
        clean_title = raw_title.strip()

    return {
        "title": clean_title,
        "due_date": extracted_date,
        "due_time": extracted_time,
        "duration_minutes": explicit_duration if explicit_duration is not None else extracted_duration
    }


def get_deadline_info(task: dict):
    """
    Computes time remaining until deadline, human-readable tag, and ANSI color code.
    Visual Task Ageing Rules:
    - Untimed tasks inherit Midnight (23:59:59) and follow pure absolute countdown:
      * >3h to midnight: Clean calm dash '-' in C_GRAY
      * <=3h to midnight (10800s): [SOON: Xh Ym] in C_B_YELLOW
      * <=90m to midnight (5400s): [URGENT: Xh Ym] in C_ORANGE
      * <=45m to midnight (2700s): [CRITICAL: Xm LEFT] in C_B_BLINK_RED
      * <0s: [OVERDUE: Xm AGO] in C_INV_RED
    - Timed tasks (--due) follow dynamic progression with hard absolute ceilings:
      * CRITICAL is strictly capped at <= 45m remaining (never triggers with >45m left).
      * URGENT is strictly capped at <= 90m remaining.
      * For micro-tasks (total window <= 45m), percentage gates prevent instant critical alerts at creation.
      * Calm Green when plenty of time remains (>3h and <70%).
    """
    now = get_local_now()
    due_time_str = task.get("due_time")
    task_date_str = task.get("task_date") or get_local_date_str()

    if task.get("done"):
        return (999999, "DONE", C_GRAY)

    has_due = bool(due_time_str)

    try:
        ty, tm, td = map(int, task_date_str.split("-"))
        if has_due:
            dh, dm = map(int, due_time_str.split(":"))
            due_dt = datetime(ty, tm, td, dh, dm, 0)

            # Estimate total window for percentage calculation
            created_at_raw = task.get("created_at")
            if created_at_raw:
                try:
                    c_clean = str(created_at_raw).replace("Z", "+00:00")
                    c_dt = datetime.fromisoformat(c_clean.split("+")[0])
                    total_window_sec = max(60.0, (due_dt - c_dt).total_seconds())
                except Exception:
                    total_window_sec = max(60.0, (due_dt - datetime(ty, tm, td, 0, 0, 0)).total_seconds())
            else:
                total_window_sec = max(60.0, (due_dt - datetime(ty, tm, td, 0, 0, 0)).total_seconds())

            diff_sec = int((due_dt - now).total_seconds())
            elapsed_sec = max(0.0, total_window_sec - diff_sec)
            pct_to_due = min(1.0, max(0.0, elapsed_sec / total_window_sec))
        else:
            due_dt = datetime(ty, tm, td, 23, 59, 59)
            diff_sec = int((due_dt - now).total_seconds())
            total_window_sec = 86400.0
            pct_to_due = 0.0

    except Exception:
        diff_sec = 86400
        has_due = False
        pct_to_due = 0.0
        total_window_sec = 86400.0

    # 1. Overdue: < 0s
    if diff_sec < 0:
        overdue_min = max(1, abs(diff_sec) // 60)
        return (diff_sec, f"[OVERDUE: {overdue_min}m AGO]", C_INV_RED)

    # -------------------------------------------------------------
    # Case A: Untimed Tasks (Inherit Midnight Wipe)
    # Pure absolute countdown to midnight — no artificial percentage penalty!
    # -------------------------------------------------------------
    if not has_due:
        if diff_sec <= 2700:  # <= 45m
            rem_m = max(0, diff_sec // 60)
            return (diff_sec, f"[CRITICAL: {rem_m}m LEFT]", C_B_BLINK_RED)

        if diff_sec <= 5400:  # <= 90m (1h 30m)
            rem_h = diff_sec // 3600
            rem_m = (diff_sec % 3600) // 60
            tag = f"[URGENT: {rem_h}h {rem_m}m]" if rem_h > 0 else f"[URGENT: {rem_m}m]"
            return (diff_sec, tag, C_ORANGE)

        if diff_sec <= 10800:  # <= 3h
            rem_h = diff_sec // 3600
            rem_m = (diff_sec % 3600) // 60
            tag = f"[SOON: {rem_h}h {rem_m}m]" if rem_h > 0 else f"[SOON: {rem_m}m]"
            return (diff_sec, tag, C_B_YELLOW)

        # Untimed task during calm daytime hours (>3h to midnight)
        return (diff_sec, "-", C_GRAY)

    # -------------------------------------------------------------
    # Case B: Timed Tasks (--due specified)
    # Dynamic percentage progression with HARD absolute ceilings
    # -------------------------------------------------------------
    # Hard Ceiling: CRITICAL is strictly restricted to <= 45m remaining.
    # For micro-tasks (total window <= 45m), requires >= 90% elapsed or <= 10m remaining.
    # For macro-tasks (total window > 45m), triggers if <= 30m OR (diff_sec <= 45m and pct >= 0.90).
    is_critical = False
    if diff_sec <= 2700:  # Must be within 45 minutes
        if total_window_sec <= 2700:
            is_critical = (pct_to_due >= 0.90 or diff_sec <= 300)
        else:
            is_critical = (diff_sec <= 1800 or pct_to_due >= 0.90)

    if is_critical:
        rem_m = max(0, diff_sec // 60)
        return (diff_sec, f"[CRITICAL: {rem_m}m LEFT]", C_B_BLINK_RED)

    # Hard Ceiling: URGENT is strictly restricted to <= 90m remaining.
    is_urgent = False
    if diff_sec <= 5400:  # Must be within 90 minutes
        if total_window_sec <= 5400:
            is_urgent = (pct_to_due >= 0.75 or diff_sec <= 900)
        else:
            is_urgent = (diff_sec <= 3600 or pct_to_due >= 0.85)

    if is_urgent:
        rem_h = diff_sec // 3600
        rem_m = (diff_sec % 3600) // 60
        tag = f"[URGENT: {rem_h}h {rem_m}m]" if rem_h > 0 else f"[URGENT: {rem_m}m]"
        return (diff_sec, tag, C_ORANGE)

    # Warning Bright Yellow: <= 3h remaining OR >= 70% to due time
    if diff_sec <= 10800 or pct_to_due >= 0.70:
        rem_h = diff_sec // 3600
        rem_m = (diff_sec % 3600) // 60
        tag = f"[SOON: {rem_h}h {rem_m}m]" if rem_h > 0 else f"[SOON: {rem_m}m]"
        return (diff_sec, tag, C_B_YELLOW)

    # Calm Green: > 3h and < 70%
    rem_h = diff_sec // 3600
    tag = f"({task['due_time']} | {rem_h}h left)" if rem_h <= 5 else f"({task['due_time']})"
    return (diff_sec, tag, C_GREEN)

# 5. CLI Command Implementations
def cli_add(args):
    """
    Syntax: add <title> [--due HH:MM] [--duration Xm] [-s | --sub <subtask_title> ...]
    Adds a new task with optional deadline, target duration, and one-shot subtasks.
    """
    if not args:
        return f"{C_RED}Error: Task title required. Usage: add <title> [--due HH:MM] [--duration Xm] [-s <subtask>]{C_RESET}"

    due_time = None
    due_date_override = None
    duration_min = None
    subtask_titles = []
    title_words = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--due" and i + 1 < len(args):
            raw_due = args[i + 1]
            p_date, p_time = parse_due_input(raw_due)
            if not p_date and not p_time:
                return f"{C_RED}Error: Invalid due time format '{raw_due}'. Use HH:MM, 6pm, tomorrow, or 'tomorrow 6pm'.{C_RESET}"
            if p_date:
                due_date_override = p_date
            due_time = p_time
            i += 2
        elif arg == "--duration" and i + 1 < len(args):
            duration_min = parse_duration(args[i + 1])
            if not duration_min:
                return f"{C_RED}Error: Invalid duration format '{args[i + 1]}'. Use 45m, 1h, or 1h30m.{C_RESET}"
            i += 2
        elif (arg in ("--sub", "-s", "--subtask")) and i + 1 < len(args):
            sub_title = sanitize_text(args[i + 1])
            if sub_title:
                subtask_titles.append(sub_title)
            i += 2
        else:
            title_words.append(arg)
            i += 1

    raw_title_candidate = sanitize_text(" ".join(title_words))
    if not raw_title_candidate:
        return f"{C_RED}Error: Task title required.{C_RESET}"

    # Natural Language Parsing on Primary Task Title with Flag Precedence
    has_explicit_due = (due_date_override is not None) or (due_time is not None)
    nlp_task = parse_natural_task(
        raw_title_candidate,
        explicit_due="explicit" if has_explicit_due else None,
        explicit_duration=duration_min,
        now=get_local_now()
    )
    title = nlp_task["title"]
    if not due_date_override and nlp_task["due_date"]:
        due_date_override = nlp_task["due_date"]
    if not due_time and nlp_task["due_time"]:
        due_time = nlp_task["due_time"]
    if duration_min is None and nlp_task["duration_minutes"]:
        duration_min = nlp_task["duration_minutes"]

    purge_expired_tasks()
    todos = get_local_todos()
    now_iso = datetime.now(timezone.utc).isoformat()
    today_date = get_local_date_str()
    task_date = due_date_override or today_date

    # Sequential monotonic integer ID: 1, 2, 3...
    existing_nums = [int(t["id"]) for t in todos if str(t.get("id", "")).isdigit()]
    task_id = str(max(existing_nums, default=0) + 1)
    backend_uuid = str(uuid.uuid4())

    subtasks = []
    for idx, stitle in enumerate(subtask_titles):
        nlp_sub = parse_natural_task(stitle, now=get_local_now())
        subtasks.append({
            "id": f"{task_id}.{idx + 1}",
            "uuid": str(uuid.uuid4()),
            "title": nlp_sub["title"],
            "due_time": nlp_sub["due_time"],
            "duration_minutes": nlp_sub["duration_minutes"],
            "done": False,
            "created_at": now_iso,
            "updated_at": now_iso
        })

    new_task = {
        "id": task_id,
        "uuid": backend_uuid,
        "pairing_code": get_pairing_code() or "",
        "task_date": task_date,
        "title": title,
        "due_time": due_time,
        "duration_minutes": duration_min,
        "done": False,
        "subtasks": subtasks,
        "created_at": now_iso,
        "updated_at": now_iso,
        "synced": False
    }

    todos.append(new_task)
    save_local_todos(todos)

    try:
        window.PyTodoBridge.playSound("add")
    except Exception:
        pass
    try:
        window.PyTodoBridge.triggerBackgroundSync()
    except Exception:
        pass

    meta = []
    if due_date_override and due_date_override != today_date:
        meta.append(f"Date: {C_CYAN}{due_date_override}{C_RESET}")
    if due_time:
        meta.append(f"Due: {C_YELLOW}{due_time}{C_RESET}")
    if duration_min:
        meta.append(f"Est: {C_CYAN}{duration_min}m{C_RESET}")
    meta_str = f" ({', '.join(meta)})" if meta else ""

    lines = [f"{C_GREEN}[+] Task added:{C_RESET} [{C_CYAN}{task_id}{C_RESET}] {title}{meta_str}"]
    for idx, s in enumerate(subtasks):
        branch = "└─" if idx == len(subtasks) - 1 else "├─"
        s_meta = []
        if s.get("due_time"):
            s_meta.append(f"Due: {C_YELLOW}{s['due_time']}{C_RESET}")
        if s.get("duration_minutes"):
            s_meta.append(f"Est: {C_CYAN}{s['duration_minutes']}m{C_RESET}")
        s_meta_str = f" ({', '.join(s_meta)})" if s_meta else ""
        lines.append(f"  {C_GRAY}{branch}{C_RESET} [{C_CYAN}{s['id']}{C_RESET}] {s['title']}{s_meta_str}")

    return "\n".join(lines)

def cli_ls(args):
    """
    Syntax: ls (or heatmap / today)
    Displays active tasks with subtask hierarchy, visual heatmaps, and progress badges.
    """
    purge_expired_tasks()
    todos = get_local_todos()
    if not todos:
        return f"{C_GRAY}(No tasks for today. Type 'add <title>' to create one){C_RESET}"

    term_width = get_terminal_width()
    total_cnt = len(todos)
    done_cnt = sum(1 for t in todos if t.get("done"))
    pct = (done_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0

    now = get_local_now()
    sec_left = 86400 - (now.hour * 3600 + now.minute * 60 + now.second)
    h_left = max(0, sec_left // 3600)
    m_left = max(0, (sec_left % 3600) // 60)

    # 1-Line ASCII Progress Summary (responsively fitted to terminal width)
    if term_width < 45:
        bar_w = max(4, min(10, term_width - 18))
        filled = int((pct / 100.0) * bar_w)
        prog_bar = f"{C_GREEN}" + ("=" * filled) + ">" + ("." * max(0, bar_w - filled - 1)) + f"{C_RESET}"
        progress_summary = f"{C_DIM}[{prog_bar}] {pct:3.0f}% ({done_cnt}/{total_cnt}){C_RESET}"
    elif term_width < 68:
        bar_w = max(5, min(10, term_width - 26))
        filled = int((pct / 100.0) * bar_w)
        prog_bar = f"{C_GREEN}" + ("=" * filled) + ">" + ("." * max(0, bar_w - filled - 1)) + f"{C_RESET}"
        progress_summary = f"{C_DIM}[{prog_bar}] {pct:3.0f}% ({done_cnt}/{total_cnt}) | {h_left:02d}h{m_left:02d}m{C_RESET}"
    else:
        bar_w = max(8, min(22, term_width - 48))
        filled = int((pct / 100.0) * bar_w)
        prog_bar = f"{C_GREEN}" + ("=" * filled) + ">" + ("." * max(0, bar_w - filled - 1)) + f"{C_RESET}"
        progress_summary = f"{C_DIM}[{prog_bar}] {pct:3.0f}% ({done_cnt}/{total_cnt} Done) | {h_left:02d}h {m_left:02d}m to Midnight{C_RESET}"

    lines = [progress_summary]

    # Mode A: Compact Mobile Stream Mode (< 65 cols)
    if term_width < 65:
        separator_len = max(20, min(term_width, 60))
        lines.append(f"{C_GRAY}" + ("-" * separator_len) + f"{C_RESET}")

        for t in todos:
            status = f"{C_GREEN}[DONE]{C_RESET}" if t["done"] else f"{C_RED}[TODO]{C_RESET}"
            sync_st = f"{C_GREEN}✔{C_RESET}" if t.get("synced") else f"{C_YELLOW}*{C_RESET}"
            _, tag, color = get_deadline_info(t)
            badge_text = tag.strip()
            if term_width < 38 and len(badge_text) > 13:
                badge_text = badge_text[:12] + "…"
            badge = f"{color}{badge_text}{C_RESET}"

            subtasks = t.get("subtasks", [])
            sub_progress = ""
            if subtasks:
                sub_done_cnt = sum(1 for s in subtasks if s.get("done"))
                sub_progress = f" {C_DIM}[{sub_done_cnt}/{len(subtasks)}]{C_RESET}"

            dur_tag_raw = f" ({t['duration_minutes']}m)" if t.get("duration_minutes") else ""
            dur_tag = f" {C_DIM}({t['duration_minutes']}m){C_RESET}" if t.get("duration_minutes") else ""

            prefix_w = get_visual_width(f"[{t['id']}] [TODO] ")
            suffix_w = get_visual_width(dur_tag_raw) + (get_visual_width(sub_progress) if sub_progress else 0)

            if term_width - prefix_w - suffix_w < 4 and dur_tag_raw:
                dur_tag = ""
                dur_tag_raw = ""
                suffix_w = get_visual_width(sub_progress) if sub_progress else 0

            avail_title = max(4, term_width - prefix_w - suffix_w)
            safe_title = truncate_visual(t['title'], avail_title)

            if t["done"]:
                title_display = f"{C_GRAY}\x1b[9m{safe_title}\x1b[29m\x1b[0m"
            else:
                title_display = f"{C_WHITE}{safe_title}{C_RESET}"

            # Stacked 2-line clean mobile item
            lines.append(f"{C_CYAN}[{t['id']}]{C_RESET} {status} {title_display}{dur_tag}{sub_progress}")

            due_sync_line = f"    {C_DIM}Due:{C_RESET} {badge}  {C_DIM}Sync:{C_RESET} {sync_st}"
            if get_visual_width(due_sync_line) > term_width:
                due_sync_line = f"    {C_DIM}Due:{C_RESET} {badge} {sync_st}"
                if get_visual_width(due_sync_line) > term_width:
                    avail_badge = max(4, term_width - 14)
                    badge_compact = f"{color}{truncate_visual(tag.strip(), avail_badge)}{C_RESET}"
                    due_sync_line = f"    {C_DIM}Due:{C_RESET} {badge_compact} {sync_st}"
            lines.append(due_sync_line)

            if subtasks:
                for idx, sub in enumerate(subtasks):
                    is_last = (idx == len(subtasks) - 1)
                    branch = "└── " if is_last else "├── "
                    sub_done = bool(sub.get("done"))
                    glyph = f"{C_GREEN}[✓]{C_RESET}" if sub_done else f"{C_AMBER}[○]{C_RESET}"
                    sub_id = f"{C_CYAN}{sub['id']}{C_RESET}"

                    sub_meta = []
                    if sub.get("due_time") and not sub_done:
                        _, s_tag, s_color = get_deadline_info(sub)
                        sub_meta.append(f"{s_color}{s_tag.strip()}{C_RESET}")
                    elif sub.get("due_time"):
                        sub_meta.append(f"{C_GRAY}({sub['due_time']}){C_RESET}")
                    if sub.get("duration_minutes"):
                        sub_meta.append(f"{C_DIM}{sub['duration_minutes']}m{C_RESET}")
                    sub_meta_str = f" ({', '.join(sub_meta)})" if sub_meta else ""

                    prefix_w = get_visual_width(f"    {branch}[✓] {sub['id']} ")
                    suffix_w = get_visual_width(sub_meta_str)
                    avail_title = max(4, term_width - prefix_w - suffix_w)

                    safe_title = truncate_visual(sub.get("title", ""), avail_title)
                    if sub_done:
                        styled_title = f"{C_GRAY}\x1b[9m{safe_title}\x1b[29m\x1b[0m"
                    else:
                        styled_title = f"{C_WHITE}{safe_title}{C_RESET}"
                    lines.append(f"    {C_GRAY}{branch}{C_RESET}{glyph} {sub_id} {styled_title}{sub_meta_str}")

        return "\n".join(lines)

    # Mode B: Standard Table Mode (>= 65 cols)
    separator_len = max(50, min(term_width, 160))
    lines.append(f"{C_BOLD}ID    STATUS   SYNC  DEADLINE / HEATMAP    TASK{C_RESET}")
    lines.append(f"{C_GRAY}" + ("-" * separator_len) + f"{C_RESET}")

    for t in todos:
        status = f"{C_GREEN}[DONE]{C_RESET}" if t["done"] else f"{C_RED}[TODO]{C_RESET}"
        sync_st = f"{C_GREEN}✔{C_RESET}" if t.get("synced") else f"{C_YELLOW}*{C_RESET}"

        _, tag, color = get_deadline_info(t)
        badge = f"{color}{pad_string(tag, 21)}{C_RESET}"

        subtasks = t.get("subtasks", [])
        sub_progress = ""
        if subtasks:
            done_cnt = sum(1 for s in subtasks if s.get("done"))
            if term_width < 80:
                sub_progress = f" {C_DIM}[{done_cnt}/{len(subtasks)}]{C_RESET}"
            else:
                sub_progress = f" {C_DIM}[{done_cnt}/{len(subtasks)} done]{C_RESET}"

        dur_tag = f" {C_DIM}({t['duration_minutes']}m){C_RESET}" if t.get("duration_minutes") else ""
        
        # Truncate parent title in Mode B to prevent wrapping across rows
        prefix_len = 43  # ID (6) + STATUS (6) + "   " (3) + SYNC (1) + "     " (5) + badge (21) + " " (1)
        suffix_w = get_visual_width(f"{dur_tag}{sub_progress}")
        if term_width - prefix_len - suffix_w < 6 and dur_tag:
            dur_tag = ""
            suffix_w = get_visual_width(sub_progress)

        avail_title = max(4, term_width - prefix_len - suffix_w)
        safe_title = truncate_visual(t['title'], avail_title)

        if t["done"]:
            title_display = f"{C_GRAY}\x1b[9m{safe_title}\x1b[29m\x1b[0m"
        else:
            title_display = f"{C_WHITE}{safe_title}{C_RESET}"

        lines.append(f"{C_CYAN}{t['id']:<6}{C_RESET}{status}   {sync_st}     {badge} {title_display}{dur_tag}{sub_progress}")

        # Option C: Nested Subtask Hierarchy aligned inside the TASK column
        if subtasks:
            if term_width >= 100:
                indent = " " * 49
            else:
                indent = " " * 43

            for idx, sub in enumerate(subtasks):
                is_last = (idx == len(subtasks) - 1)
                branch = "└── " if is_last else "├── "
                sub_done = bool(sub.get("done"))

                glyph = f"{C_GREEN}[✓]{C_RESET}" if sub_done else f"{C_AMBER}[○]{C_RESET}"
                sub_id = f"{C_CYAN}{sub['id']:<4}{C_RESET}"

                sub_meta = []
                if sub.get("due_time") and not sub_done:
                    _, s_tag, s_color = get_deadline_info(sub)
                    sub_meta.append(f"{s_color}{s_tag.strip()}{C_RESET}")
                elif sub.get("due_time"):
                    sub_meta.append(f"{C_GRAY}({sub['due_time']}){C_RESET}")
                if sub.get("duration_minutes"):
                    sub_meta.append(f"{C_DIM}{sub['duration_minutes']}m{C_RESET}")
                sub_meta_str = f" ({', '.join(sub_meta)})" if sub_meta else ""

                prefix_w = get_visual_width(f"{indent}{branch}[✓] {sub['id']:<4} ")
                suffix_w = get_visual_width(sub_meta_str)
                avail_title = max(4, term_width - prefix_w - suffix_w)

                raw_title = sub.get("title", "")
                safe_sub_title = truncate_visual(raw_title, avail_title)
                if sub_done:
                    styled_title = f"{C_GRAY}\x1b[9m{safe_sub_title}\x1b[29m\x1b[0m"
                else:
                    styled_title = f"{C_WHITE}{safe_sub_title}{C_RESET}"

                lines.append(f"{indent}{C_GRAY}{branch}{C_RESET}{glyph} {sub_id} {styled_title}{sub_meta_str}")

    return "\n".join(lines)

def cli_done(args):
    """
    Syntax: done <id> (e.g. done 1, done 1.1, done 1 1, or multi-target: done 1.1 1.2)
    Marks task(s) or subtask(s) completed. Cascades completion.
    """
    if not args:
        return f"{C_RED}Error: Task or subtask ID required. Example: done 1 or done 1.1 or done 1 1{C_RESET}"

    todos = get_local_todos()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Handle space notation: done 1 1 -> done 1.1
    targets = []
    i = 0
    while i < len(args):
        a = args[i].strip()
        if i + 1 < len(args) and a.isdigit() and args[i+1].strip().isdigit() and "." not in a:
            targets.append(f"{a}.{args[i+1].strip()}")
            i += 2
        else:
            targets.append(a)
            i += 1

    results = []
    sound_to_play = None

    for target_id in targets:
        # Case A: Subtask completion
        if "." in target_id:
            parent_id, sub_idx_str = target_id.split(".", 1)
            found = False
            for t in todos:
                if t["id"] == parent_id or t.get("uuid") == parent_id:
                    subtasks = t.get("subtasks", [])
                    for sub in subtasks:
                        if sub["id"] == target_id or sub["id"] == f"{parent_id}.{sub_idx_str}":
                            sub["done"] = True
                            sub["updated_at"] = now_iso
                            t["updated_at"] = now_iso
                            t["synced"] = False

                            # If all subtasks under parent are done, mark parent done as well
                            if all(s.get("done") for s in subtasks):
                                t["done"] = True
                                sound_to_play = "done"
                            elif not sound_to_play:
                                sound_to_play = "subtask"

                            results.append(f"{C_GREEN}[✔] Subtask completed:{C_RESET} [{C_CYAN}{target_id}{C_RESET}] {sub['title']}")
                            found = True
                            break
                if found:
                    break
            if not found:
                results.append(f"{C_RED}Error: Subtask '{target_id}' not found.{C_RESET}")
        else:
            # Case B: Parent task completion
            found = False
            for t in todos:
                if t["id"] == target_id or t.get("uuid") == target_id:
                    t["done"] = True
                    t["updated_at"] = now_iso
                    t["synced"] = False
                    # Cascade completion to all child subtasks
                    for sub in t.get("subtasks", []):
                        sub["done"] = True
                        sub["updated_at"] = now_iso
                    sound_to_play = "done"
                    results.append(f"{C_GREEN}[✔] Task completed:{C_RESET} [{C_CYAN}{target_id}{C_RESET}] {t['title']}")
                    found = True
                    break
            if not found:
                results.append(f"{C_RED}Error: Task ID '{target_id}' not found.{C_RESET}")

    save_local_todos(todos)
    try:
        total_cnt = len(todos)
        done_cnt = sum(1 for t in todos if t.get("done"))
        if sound_to_play and total_cnt > 0 and done_cnt == total_cnt:
            sound_to_play = "celebration"

        if sound_to_play:
            window.PyTodoBridge.playSound(sound_to_play)
        window.PyTodoBridge.triggerBackgroundSync()
    except Exception:
        pass

    return "\n".join(results)

def cli_undone(args):
    """
    Syntax: undone <id> (e.g. undone 1, undone 1.1, undone 1 1)
    Reverts a completed task or subtask to incomplete [TODO].
    If a subtask is marked incomplete, its parent is also reverted to incomplete.
    """
    if not args:
        return f"{C_RED}Error: Task or subtask ID required. Example: undone 1 or undone 1.1{C_RESET}"

    todos = get_local_todos()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Handle space notation: undone 1 1 -> undone 1.1
    if len(args) >= 2 and args[0].isdigit() and args[1].isdigit() and "." not in args[0]:
        target_id = f"{args[0]}.{args[1]}"
    else:
        target_id = args[0].strip()

    # Case A: Revert Subtask
    if "." in target_id:
        parent_id, sub_idx_str = target_id.split(".", 1)
        for t in todos:
            if t["id"] == parent_id or t.get("uuid") == parent_id:
                subtasks = t.get("subtasks", [])
                for sub in subtasks:
                    if sub["id"] == target_id or sub["id"] == f"{parent_id}.{sub_idx_str}":
                        sub["done"] = False
                        sub["updated_at"] = now_iso
                        # Parent must revert to incomplete if any subtask is incomplete
                        t["done"] = False
                        t["updated_at"] = now_iso
                        t["synced"] = False
                        save_local_todos(todos)
                        try:
                            window.PyTodoBridge.playSound("undone")
                        except Exception:
                            pass
                        try:
                            window.PyTodoBridge.triggerBackgroundSync()
                        except Exception:
                            pass
                        return f"{C_YELLOW}[○] Subtask reverted to incomplete:{C_RESET} [{C_CYAN}{target_id}{C_RESET}] {sub['title']}"
        return f"{C_RED}Error: Subtask '{target_id}' not found.{C_RESET}"

    # Case B: Revert Parent Task
    for t in todos:
        if t["id"] == target_id or t.get("uuid") == target_id:
            t["done"] = False
            t["updated_at"] = now_iso
            t["synced"] = False
            for sub in t.get("subtasks", []):
                sub["done"] = False
                sub["updated_at"] = now_iso
            save_local_todos(todos)
            try:
                window.PyTodoBridge.playSound("undone")
            except Exception:
                pass
            try:
                window.PyTodoBridge.triggerBackgroundSync()
            except Exception:
                pass
            return f"{C_YELLOW}[○] Task reverted to incomplete:{C_RESET} [{C_CYAN}{target_id}{C_RESET}] {t['title']}"

    return f"{C_RED}Error: Task ID '{target_id}' not found.{C_RESET}"

def cli_edit(args):
    """
    Syntax: edit <id> [options]
    Options:
      --title <new title> (or simply write the title without --title)
      --due <time or date> (e.g. 18:00, 6pm, 6:00 pm, tomorrow, 2026-09-19)
      --date <date> (e.g. 2026-09-19, tomorrow, today)
      --duration <minutes> (e.g. 45m, 1h, or plain number 45)
      --clear-due / --clear-date
      --clear-duration
      --add-sub <subtask_title>
      --rm-sub <subtask_id_or_number>
    Also supports editing subtasks directly: edit 1.1 <new title>
    """
    if not args:
        return f"{C_RED}Error: Task ID required. Usage: edit <id> [options]{C_RESET}"

    # Handle space notation for subtask IDs: edit 1 1 ... -> target '1.1'
    if len(args) >= 2 and args[0].isdigit() and args[1].isdigit() and "." not in args[0]:
        target_id = f"{args[0]}.{args[1]}"
        rem = args[2:]
    else:
        target_id = args[0].strip()
        rem = args[1:]

    todos = get_local_todos()
    is_subtask = "." in target_id
    parent_task = None
    target_sub = None
    target_task = None

    if is_subtask:
        parent_id, _ = target_id.split(".", 1)
        for t in todos:
            if t["id"] == parent_id or t.get("uuid") == parent_id:
                parent_task = t
                for s in t.get("subtasks", []):
                    if s["id"] == target_id:
                        target_sub = s
                        break
                break
        if not parent_task:
            return f"{C_RED}Error: Parent task '{parent_id}' not found.{C_RESET}"
        if not target_sub:
            return f"{C_RED}Error: Subtask '{target_id}' not found.{C_RESET}"
    else:
        for t in todos:
            if t["id"] == target_id or t.get("uuid") == target_id:
                target_task = t
                break
        if not target_task:
            return f"{C_RED}Error: Task ID '{target_id}' not found.{C_RESET}"

    if not rem:
        return f"{C_YELLOW}No changes specified for '{target_id}'. Usage: edit {target_id} [new title] [--due HH:MM] [--duration Xm]{C_RESET}"

    # Helper to recognize flags strictly by dash prefix
    def is_flag_token(tok):
        return tok.startswith("-")

    parsed_actions = {}
    i = 0

    # If rem starts with non-flag words, capture them as the title!
    if not is_flag_token(rem[0]):
        title_tokens = []
        while i < len(rem) and not is_flag_token(rem[i]):
            title_tokens.append(rem[i])
            i += 1
        parsed_actions["title"] = " ".join(title_tokens)

    while i < len(rem):
        tok = rem[i].lower()
        if tok in ("--title", "-title", "-t"):
            vals = []
            i += 1
            while i < len(rem) and not is_flag_token(rem[i]):
                vals.append(rem[i])
                i += 1
            if vals:
                parsed_actions["title"] = " ".join(vals)
        elif tok in ("--due", "-due", "--time", "-time", "--date", "-date", "--due-date", "-due-date"):
            vals = []
            i += 1
            while i < len(rem) and not is_flag_token(rem[i]):
                vals.append(rem[i])
                i += 1
            if vals:
                parsed_actions["due_raw"] = " ".join(vals)
        elif tok in ("--duration", "-duration", "--dur", "-dur", "-d"):
            vals = []
            i += 1
            while i < len(rem) and not is_flag_token(rem[i]):
                vals.append(rem[i])
                i += 1
            if vals:
                parsed_actions["duration_raw"] = " ".join(vals)
        elif tok in ("--clear-due", "-clear-due", "--clear-date", "-clear-date"):
            parsed_actions["clear_due"] = True
            i += 1
        elif tok in ("--clear-duration", "-clear-duration", "--clear-dur", "-clear-dur"):
            parsed_actions["clear_duration"] = True
            i += 1
        elif tok in ("--add-sub", "-add-sub", "--sub", "-s", "--subtask", "-subtask"):
            vals = []
            i += 1
            while i < len(rem) and not is_flag_token(rem[i]):
                vals.append(rem[i])
                i += 1
            if vals:
                parsed_actions["add_sub"] = " ".join(vals)
        elif tok in ("--rm-sub", "-rm-sub", "--del-sub", "-del-sub"):
            if i + 1 < len(rem):
                parsed_actions["rm_sub"] = rem[i + 1].strip()
                i += 2
            else:
                i += 1
        else:
            i += 1

    if not parsed_actions:
        return f"{C_YELLOW}No changes specified. Use --title, --due, --duration, --add-sub, or --rm-sub.{C_RESET}"

    now_iso = datetime.now(timezone.utc).isoformat()
    changes = []

    # Case A: Editing a subtask
    if is_subtask:
        if "title" in parsed_actions:
            new_title = sanitize_text(parsed_actions["title"])
            if new_title:
                target_sub["title"] = new_title
                changes.append(f"title -> '{new_title}'")
        target_sub["updated_at"] = now_iso
        parent_task["updated_at"] = now_iso
        parent_task["synced"] = False
        save_local_todos(todos)
        try:
            window.PyTodoBridge.triggerBackgroundSync()
        except Exception:
            pass
        return f"{C_GREEN}[✔] Subtask '{target_id}' updated:{C_RESET} {', '.join(changes)}"

    # Case B: Editing a main task
    if "title" in parsed_actions:
        new_title = sanitize_text(parsed_actions["title"])
        if new_title:
            target_task["title"] = new_title
            changes.append(f"title -> '{new_title}'")

    if "due_raw" in parsed_actions:
        due_val = parsed_actions["due_raw"]
        new_date, new_time = parse_due_input(due_val)
        if not new_date and not new_time:
            return f"{C_RED}Error: Invalid due format '{due_val}'. Use 18:00, 6pm, tomorrow, or 2026-09-19.{C_RESET}"
        if new_date:
            target_task["task_date"] = new_date
            changes.append(f"date -> {new_date}")
        if new_time:
            target_task["due_time"] = new_time
            changes.append(f"due -> {new_time}")

    if parsed_actions.get("clear_due"):
        target_task["due_time"] = None
        changes.append("due cleared")

    if "duration_raw" in parsed_actions:
        dur_val = parsed_actions["duration_raw"]
        dur = parse_duration(dur_val)
        if not dur:
            return f"{C_RED}Error: Invalid duration '{dur_val}'. Use 30, 45m, 1h, or 1h30m.{C_RESET}"
        target_task["duration_minutes"] = dur
        changes.append(f"duration -> {dur}m")

    if parsed_actions.get("clear_duration"):
        target_task["duration_minutes"] = None
        changes.append("duration cleared")

    if "add_sub" in parsed_actions:
        sub_title = sanitize_text(parsed_actions["add_sub"])
        if sub_title:
            subtasks = target_task.setdefault("subtasks", [])
            existing_sub_indices = []
            for s in subtasks:
                if isinstance(s, dict) and "." in str(s.get("id", "")):
                    try:
                        existing_sub_indices.append(int(str(s["id"]).split(".", 1)[1]))
                    except ValueError:
                        pass
            next_sub_num = max(existing_sub_indices, default=0) + 1
            sub_id = f"{target_task['id']}.{next_sub_num}"
            nlp_sub = parse_natural_task(sub_title, now=get_local_now())
            subtasks.append({
                "id": sub_id,
                "uuid": str(uuid.uuid4()),
                "title": nlp_sub["title"],
                "due_time": nlp_sub["due_time"],
                "duration_minutes": nlp_sub["duration_minutes"],
                "done": False,
                "created_at": now_iso,
                "updated_at": now_iso
            })
            if target_task.get("done", False):
                target_task["done"] = False
                changes.append("reopened task (new incomplete subtask)")
            s_meta = []
            if nlp_sub.get("due_time"):
                s_meta.append(f"Due: {nlp_sub['due_time']}")
            if nlp_sub.get("duration_minutes"):
                s_meta.append(f"Est: {nlp_sub['duration_minutes']}m")
            s_meta_str = f" ({', '.join(s_meta)})" if s_meta else ""
            changes.append(f"added subtask [{sub_id}]{s_meta_str}")

    if "rm_sub" in parsed_actions:
        target_sub_id = parsed_actions["rm_sub"]
        subtasks = target_task.get("subtasks", [])
        idx_to_remove = None
        for idx, s in enumerate(subtasks):
            if s.get("id") == target_sub_id or str(idx + 1) == target_sub_id or f"{target_task['id']}.{idx + 1}" == target_sub_id:
                idx_to_remove = idx
                break
        if idx_to_remove is not None:
            removed = subtasks.pop(idx_to_remove)
            # Stable Monotonic IDs: do NOT renumber remaining subtasks
            if len(subtasks) > 0 and all(s.get("done") for s in subtasks if isinstance(s, dict)):
                target_task["done"] = True
                changes.append("marked task complete (all remaining subtasks done)")
            changes.append(f"removed subtask '{removed['title']}'")
        else:
            return f"{C_RED}Error: Subtask '{target_sub_id}' not found.{C_RESET}"

    if not changes:
        return f"{C_YELLOW}No changes applied.{C_RESET}"

    target_task["updated_at"] = now_iso
    target_task["synced"] = False
    save_local_todos(todos)

    try:
        window.PyTodoBridge.triggerBackgroundSync()
    except Exception:
        pass

    return f"{C_GREEN}[✔] Task '{target_id}' updated:{C_RESET} {', '.join(changes)}"

def generate_unique_pairing_code() -> str:
    """Generates a collision-resistant 6-character pairing code excluding ambiguous chars (0/O, 1/I, L)."""
    chars = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    rand_int = uuid.uuid4().int
    accum = []
    base = len(chars)
    for _ in range(6):
        accum.append(chars[rand_int % base])
        rand_int //= base
    return "".join(accum)

async def cli_code(args):
    """
    Syntax: code (or link code)
    Displays the active pairing key linked to this dataset.
    """
    code = get_pairing_code()
    if not code:
        return (
            f"{C_GRAY}[○] Device is not linked to any cloud pairing key.{C_RESET}\n"
            f"{C_WHITE}Run {C_CYAN}'link generate'{C_WHITE} to create a unique 6-character cross-device key.{C_RESET}"
        )
    return (
        f"{C_GREEN}[●] Active Pairing Key:{C_RESET} {C_B_CYAN}{code}{C_RESET}\n"
        f"{C_GRAY}Run {C_WHITE}'link {code}'{C_GRAY} on your phone or laptop to sync instantly without passwords.{C_RESET}"
    )

async def cli_link(args):
    """
    Syntax: link [generate | <code> | code | status | unlink | reset]
    Frictionless 6-character Base32 cross-device pairing without email/passwords.
    """
    subcmd = args[0].lower() if args else "status"
    
    if subcmd in ("generate", "new"):
        existing_code = get_pairing_code()
        has_force = any(a.lower() in ("--force", "-f", "--confirm", "-y") for a in args[1:])
        if existing_code and not has_force:
            return (
                f"{C_YELLOW}[!] Warning: This device is already linked to pairing key {C_CYAN}{existing_code}{C_YELLOW}.{C_RESET}\n"
                f"{C_WHITE}Generating a new key will unpair this device from {C_CYAN}{existing_code}{C_WHITE} and register a new dataset key.\n"
                f"Other devices using {C_CYAN}{existing_code}{C_WHITE} will no longer sync with this device.\n"
                f"Your local tasks will be PRESERVED and re-keyed to the new code.\n\n"
                f"To confirm, run: {C_B_CYAN}link generate --force{C_RESET}"
            )

        # Atomic unique insertion loop into Supabase (up to 5 retries on collision)
        code = None
        for _ in range(5):
            candidate = generate_unique_pairing_code()
            if hasattr(window, "PyTodoBridge") and hasattr(window.PyTodoBridge, "supabaseInsertAccount"):
                try:
                    raw = await window.PyTodoBridge.supabaseInsertAccount(candidate)
                    res = json.loads(str(raw)) if raw else {}
                    if res.get("error"):
                        continue
                    code = candidate
                    break
                except Exception:
                    continue
            elif supabaseClient:
                try:
                    res = await supabaseClient.from_("todo_accounts").insert({"pairing_code": candidate}).execute()
                    if getattr(res, "error", None):
                        continue
                    code = candidate
                    break
                except Exception:
                    continue
            else:
                code = candidate
                break

        if not code:
            code = generate_unique_pairing_code()

        set_pairing_code(code)
        
        # Update existing local tasks with this pairing code
        todos = get_local_todos()
        for t in todos:
            t["pairing_code"] = code
            t["synced"] = False
        save_local_todos(todos)
        
        try:
            window.PyTodoBridge.setPairingCode(code)
            window.PyTodoBridge.triggerBackgroundSync()
        except Exception:
            pass
            
        return (
            f"{C_B_GREEN}[✔] Pairing key generated:{C_RESET} {C_B_CYAN}{code}{C_RESET}\n"
            f"{C_GRAY}Run {C_WHITE}'link {code}'{C_GRAY} on your other phone/laptop to sync instantly without passwords.{C_RESET}"
        )

    elif subcmd in ("code", "get"):
        return await cli_code(args[1:])
        
    elif subcmd == "unlink":
        set_pairing_code("")
        try:
            window.PyTodoBridge.setPairingCode("")
        except Exception:
            pass
        return f"{C_YELLOW}[!] Device unlinked. Tasks will remain local-only.{C_RESET}"

    elif subcmd in ("reset", "wipe"):
        has_force = any(a.lower() in ("--force", "-f", "--confirm", "-y") for a in args[1:])
        if not has_force:
            return (
                f"{C_RED}[CAUTION] This will permanently wipe all local tasks and generate a fresh key.{C_RESET}\n"
                f"To confirm, run: {C_B_CYAN}link reset --force{C_RESET}"
            )
        save_local_todos([])
        set_pairing_code("")
        return await cli_link(["generate", "--force"])
        
    elif subcmd == "status":
        code = get_pairing_code()
        if code:
            return f"{C_GREEN}[●] Linked to Pairing Key:{C_RESET} {C_CYAN}{code}{C_RESET}\n{C_GRAY}Type 'sync' to force cloud push/pull, or 'code' to share.{C_RESET}"
        return f"{C_GRAY}[○] Not linked to any device. Type 'link generate' or 'link <code>' to pair.{C_RESET}"
        
    else:
        # User provided a pairing code, e.g. 'link 7K9M2P' or 'link 849201'
        code = subcmd.strip().upper()
        if not re.match(r'^[A-Z0-9]{6,8}$', code):
            return f"{C_RED}Error: Pairing key must be a 6 to 8 character alphanumeric code (e.g. 'link 7K9M2P' or 'link 849201').{C_RESET}"
            
        # Pre-flight check against todo_accounts
        if hasattr(window, "PyTodoBridge") and hasattr(window.PyTodoBridge, "supabaseCheckAccount"):
            try:
                raw = await window.PyTodoBridge.supabaseCheckAccount(code)
                res = json.loads(str(raw)) if raw else {}
                if not res.get("error"):
                    rows = res.get("data") or []
                    if len(rows) == 0:
                        return f"{C_RED}Error: Pairing key '{code}' not found on server. Check the key or run 'link generate' on the primary device first.{C_RESET}"
            except Exception:
                pass
        elif supabaseClient:
            try:
                acc_res = await supabaseClient.from_("todo_accounts").select("pairing_code").eq("pairing_code", code).execute()
                if getattr(acc_res, "error", None) is None:
                    rows = acc_res.data or []
                    if len(rows) == 0:
                        return f"{C_RED}Error: Pairing key '{code}' not found on server. Check the key or run 'link generate' on the primary device first.{C_RESET}"
            except Exception:
                pass

        set_pairing_code(code)
        try:
            window.PyTodoBridge.setPairingCode(code)
        except Exception:
            pass
            
        # Immediate pull and merge
        sync_res = await cli_sync([])
        return f"{C_GREEN}[✔] Successfully linked to key {C_CYAN}{code}{C_RESET}.\n{sync_res}"

async def cli_unlink(args):
    """Shortcut alias to unlink the device."""
    return await cli_link(["unlink"] + args)

async def cli_sync(args):
    """
    Syntax: sync
    Executes batched cloud push and element-level Last-Write-Wins (LWW) pull with tombstone deletion.
    """
    pairing_code = get_pairing_code()
    if not pairing_code:
        return f"{C_YELLOW}[!] Not linked to any cloud pairing key. Run 'link generate' first.{C_RESET}"
        
    todos = get_local_todos()
    today_date = get_local_date_str()
    tombstones = get_tombstones()
    
    try:
        window.PyTodoBridge.setSyncStatus("SYNCING")
    except Exception:
        pass
        
    try:
        # 1. Process and Delete Local Tombstones from Supabase
        if tombstones:
            if hasattr(window, "PyTodoBridge") and hasattr(window.PyTodoBridge, "supabaseDeleteTombstones"):
                try:
                    await window.PyTodoBridge.supabaseDeleteTombstones(pairing_code, json.dumps(tombstones))
                except Exception:
                    pass
            elif supabaseClient:
                try:
                    await supabaseClient.from_("todos").delete().eq("pairing_code", pairing_code).in_("id", tombstones).execute()
                except Exception:
                    pass

        # 2. Pull Remote Records for pairing_code & today (filtering out tombstones)
        remote_rows = []
        if hasattr(window, "PyTodoBridge") and hasattr(window.PyTodoBridge, "supabaseFetchTodos"):
            raw = await window.PyTodoBridge.supabaseFetchTodos(pairing_code, today_date)
            res = json.loads(str(raw)) if raw else {}
            if res.get("error"):
                raise Exception(res["error"])
            remote_rows = res.get("data") or []
        elif supabaseClient:
            remote_res = await supabaseClient.from_("todos").select("*").eq("pairing_code", pairing_code).gte("task_date", today_date).execute()
            remote_rows = remote_res.data or []

        if tombstones:
            t_set = set(tombstones)
            remote_rows = [r for r in remote_rows if str(r["id"]) not in t_set]

        # 3. Element-Level Last-Write-Wins (LWW) Merge with Remote Sanitization
        def norm_ts(ts):
            return str(ts or "").replace("Z", "+00:00")

        def sanitize_remote_subtasks(subs, parent_display_id):
            if not isinstance(subs, list):
                return []
            clean = []
            for idx, s in enumerate(subs):
                if isinstance(s, dict):
                    clean.append({
                        "id": str(s.get("id") or f"{parent_display_id}.{idx + 1}"),
                        "uuid": s.get("uuid"),
                        "title": sanitize_text(s.get("title", "")),
                        "done": bool(s.get("done", False)),
                        "updated_at": norm_ts(s.get("updated_at"))
                    })
            return clean

        def merge_subtasks_lww(loc_subs, rem_subs, parent_disp_id):
            merged = []
            rem_used = set()

            for s_loc in loc_subs:
                loc_uuid = s_loc.get("uuid")
                loc_id = str(s_loc.get("id", "")).strip()
                loc_sub_idx = loc_id.split(".", 1)[1] if "." in loc_id else loc_id
                loc_title = s_loc.get("title", "").strip().lower()

                match_idx = None
                for i, s_rem in enumerate(rem_subs):
                    if i in rem_used:
                        continue
                    rem_uuid = s_rem.get("uuid")
                    rem_id = str(s_rem.get("id", "")).strip()
                    rem_sub_idx = rem_id.split(".", 1)[1] if "." in rem_id else rem_id
                    rem_title = s_rem.get("title", "").strip().lower()

                    if loc_uuid and rem_uuid and loc_uuid == rem_uuid:
                        match_idx = i
                        break
                    if loc_id and rem_id and (loc_id == rem_id or (loc_sub_idx and loc_sub_idx == rem_sub_idx)):
                        match_idx = i
                        break
                    if loc_title and rem_title and loc_title == rem_title:
                        match_idx = i
                        break

                if match_idx is not None:
                    rem_used.add(match_idx)
                    s_rem = rem_subs[match_idx]
                    loc_ts = norm_ts(s_loc.get("updated_at"))
                    rem_ts = norm_ts(s_rem.get("updated_at"))
                    chosen = s_rem if rem_ts > loc_ts else s_loc
                    merged.append({
                        "id": s_loc.get("id") or s_rem.get("id") or "",
                        "uuid": s_loc.get("uuid") or s_rem.get("uuid") or str(uuid.uuid4()),
                        "title": chosen.get("title", ""),
                        "done": bool(chosen.get("done")),
                        "updated_at": max(loc_ts, rem_ts)
                    })
                else:
                    merged.append(s_loc)

            for i, s_rem in enumerate(rem_subs):
                if i not in rem_used:
                    merged.append(s_rem)

            existing_sub_indices = []
            for s in merged:
                cur_id = str(s.get("id", "")).strip()
                if "." in cur_id:
                    try:
                        existing_sub_indices.append(int(cur_id.split(".", 1)[1]))
                    except ValueError:
                        pass
            next_idx = max(existing_sub_indices, default=0) + 1
            for s in merged:
                if not s.get("id") or not str(s["id"]).startswith(f"{parent_disp_id}."):
                    s["id"] = f"{parent_disp_id}.{next_idx}"
                    next_idx += 1
                if not s.get("uuid"):
                    s["uuid"] = str(uuid.uuid4())
            return merged

        local_map_by_uuid = {t.get("uuid") or t["id"]: t for t in todos}
        local_map_by_id = {t["id"]: t for t in todos}
        existing_numeric_ids = [int(t["id"]) for t in todos if str(t.get("id", "")).isdigit()]
        next_num_id = max(existing_numeric_ids, default=0) + 1

        for r in remote_rows:
            rid = str(r["id"])
            clean_title = sanitize_text(r.get("title", ""))
            r_updated = norm_ts(r.get("updated_at"))

            loc = local_map_by_uuid.get(rid) or local_map_by_id.get(rid)
            if not loc:
                disp_id = str(next_num_id)
                next_num_id += 1
                clean_subs = sanitize_remote_subtasks(r.get("subtasks"), disp_id)
                new_item = {
                    "id": disp_id,
                    "uuid": rid,
                    "pairing_code": pairing_code,
                    "task_date": str(r.get("task_date") or today_date),
                    "title": clean_title,
                    "due_time": r.get("due_time"),
                    "duration_minutes": r.get("duration_minutes"),
                    "done": bool(r.get("done", False)),
                    "subtasks": clean_subs,
                    "created_at": norm_ts(r.get("created_at") or r_updated),
                    "updated_at": r_updated,
                    "synced": True
                }
                todos.append(new_item)
                local_map_by_uuid[rid] = new_item
                local_map_by_id[disp_id] = new_item
            else:
                loc_updated = norm_ts(loc.get("updated_at"))
                clean_subs = sanitize_remote_subtasks(r.get("subtasks"), loc["id"])
                merged_subs = merge_subtasks_lww(loc.get("subtasks", []), clean_subs, loc["id"])
                loc["subtasks"] = merged_subs

                if r_updated > loc_updated:
                    loc["title"] = clean_title
                    loc["due_time"] = r.get("due_time")
                    loc["duration_minutes"] = r.get("duration_minutes")
                    if merged_subs and all(s.get("done") for s in merged_subs):
                        loc["done"] = True
                    else:
                        loc["done"] = bool(r.get("done", False))
                    loc["updated_at"] = r_updated
                    loc["synced"] = True
                else:
                    if merged_subs and all(s.get("done") for s in merged_subs):
                        loc["done"] = True
                    if loc_updated > r_updated:
                        loc["synced"] = False
                    else:
                        loc["synced"] = True

        # Concurrency safety: Re-read local storage to avoid discarding in-flight additions and in-flight edits
        fresh_local = get_local_todos()
        fresh_map = {f.get("uuid") or f["id"]: f for f in fresh_local}
        current_keys = {t.get("uuid") or t["id"] for t in todos}
        tombstone_set = set(tombstones) if tombstones else set()

        for f_key, f_task in fresh_map.items():
            if f_key in tombstone_set:
                continue
            if f_key not in current_keys:
                todos.append(f_task)
                current_keys.add(f_key)
            else:
                for idx, t in enumerate(todos):
                    t_key = t.get("uuid") or t["id"]
                    if t_key == f_key:
                        if norm_ts(f_task.get("updated_at")) > norm_ts(t.get("updated_at")):
                            todos[idx] = f_task
                        break

        # 4. Batched Push of Dirty Records (with merged subtasks)
        dirty = [t for t in todos if not t.get("synced")]
        if dirty:
            batch_payload = []
            for item in dirty:
                batch_payload.append({
                    "id": item.get("uuid") or item["id"],
                    "pairing_code": pairing_code,
                    "task_date": item.get("task_date") or today_date,
                    "title": item["title"],
                    "due_time": item.get("due_time"),
                    "duration_minutes": item.get("duration_minutes"),
                    "done": item.get("done", False),
                    "subtasks": item.get("subtasks", []),
                    "updated_at": item["updated_at"]
                })
            if hasattr(window, "PyTodoBridge") and hasattr(window.PyTodoBridge, "supabaseUpsertTodos"):
                raw = await window.PyTodoBridge.supabaseUpsertTodos(json.dumps(batch_payload))
                res = json.loads(str(raw)) if raw else {}
                if res.get("error"):
                    raise Exception(res["error"])
                for item in dirty:
                    item["synced"] = True
            elif supabaseClient:
                await supabaseClient.from_("todos").upsert(batch_payload).execute()
                for item in dirty:
                    item["synced"] = True

        merged_todos = todos
        save_local_todos(merged_todos)
        
        try:
            window.PyTodoBridge.setSyncStatus("SYNCED")
        except Exception:
            pass
            
        return f"{C_GREEN}[✔] Cloud synchronization complete.{C_RESET} ({len(merged_todos)} tasks synced)"
    except Exception as err:
        try:
            window.PyTodoBridge.setSyncStatus("OFFLINE")
        except Exception:
            pass
        return f"{C_YELLOW}[!] Cloud sync paused (offline or network error): {str(err)}{C_RESET}"

def cli_sound(args):
    """
    Syntax: sound [on | off | test]
    Controls 8-bit retro audio synthesizer.
    """
    action = args[0].lower() if args else ""
    if action == "on":
        try:
            window.PyTodoBridge.setSoundEnabled(True)
            return f"{C_GREEN}[✔] 8-Bit Retro Audio FX enabled.{C_RESET}"
        except Exception:
            return f"{C_GREEN}[✔] Audio FX enabled.{C_RESET}"
    elif action == "off":
        try:
            window.PyTodoBridge.setSoundEnabled(False)
            return f"{C_GRAY}[○] Audio FX muted.{C_RESET}"
        except Exception:
            return f"{C_GRAY}[○] Audio muted.{C_RESET}"
    elif action == "test":
        try:
            window.PyTodoBridge.playSound("done")
            return f"{C_CYAN}♫ Playing test retro chime...{C_RESET}"
        except Exception as e:
            return f"{C_RED}Error: {e}{C_RESET}"
    else:
        try:
            state = "ON" if window.PyTodoBridge.isSoundEnabled() else "OFF"
            return f"{C_CYAN}Audio FX is currently {C_BOLD}{state}{C_RESET}. Type 'sound on', 'sound off', or 'sound test'."
        except Exception:
            return "Type 'sound on' or 'sound off'."

def cli_top(args):
    """
    Syntax: top [-full] (or watch [-full])
    Enters live HTOP dashboard monitor. Optional -full enables HTML5 browser fullscreen.
    """
    is_full = any(a.lower() in ("-full", "--full", "-f") for a in args)
    try:
        window.PyTodoBridge.enterDashboardMode(is_full)
        return ""
    except Exception:
        return "Live dashboard is launching..."

def handle_focus_step_command(subargs):
    """Handles configuring or viewing focus mode timer adjustment step."""
    if not subargs:
        try:
            curr_sec = int(window.PyTodoBridge.getFocusStep())
        except Exception:
            curr_sec = 300
        mins = curr_sec // 60
        secs = curr_sec % 60
        if secs:
            formatted = f"{mins}m {secs}s" if mins else f"{secs}s"
        else:
            formatted = f"{mins}m"
        return f"{C_CYAN}[i] Current focus timer step:{C_RESET} {formatted} ({curr_sec}s)"

    dur_str = subargs[0].strip()
    sec = parse_duration_seconds(dur_str)
    if not sec or sec <= 0:
        return f"{C_RED}Error: Invalid duration '{dur_str}'. Use format like 5m, 10m, 30s, 1m30s.{C_RESET}"
    if sec < 10:
        return f"{C_RED}Error: Minimum focus step is 10s.{C_RESET}"
    if sec > 7200:
        return f"{C_RED}Error: Maximum focus step is 120m (2h).{C_RESET}"

    try:
        window.PyTodoBridge.setFocusStep(sec)
        mins = sec // 60
        secs = sec % 60
        if secs:
            formatted = f"{mins}m {secs}s" if mins else f"{secs}s"
        else:
            formatted = f"{mins}m"
        return f"{C_GREEN}[✓] Focus timer adjustment step set to:{C_RESET} {formatted} ({sec}s)"
    except Exception as e:
        return f"{C_RED}Error saving focus step: {e}{C_RESET}"

def get_indexed_history():
    """
    Returns list of tuples: (h_tag, date_str, task_dict)
    Sorted by date descending, then by task id.
    """
    history = get_history_todos()
    items = []
    counter = 1
    for d in sorted(history.keys(), reverse=True):
        tasks = history[d]
        for t in tasks:
            items.append((f"H{counter}", d, t))
            counter += 1
    return items

def cli_history(args):
    """
    Syntax: history (or overdue / graveyard)
    Displays uncompleted tasks grouped under date headers.
    Retention window: 1-7 days (configurable via 'config retention <1-7>').
    """
    enforce_day_rollover()
    history = get_history_todos()
    retention_days = get_retention_days()
    today = get_local_date_str()
    try:
        today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    except Exception:
        today_dt = get_local_now().date()

    if not history or not any(history.values()):
        return (
            f"{C_BOLD}=== OVERDUE & HISTORY GRAVEYARD (Retention: {retention_days} days) ==={C_RESET}\n"
            f"{C_GRAY}No overdue tasks in history. All past tasks were completed or retention window expired.{C_RESET}\n"
            f"{C_DIM}Incomplete tasks from previous days are preserved here for {retention_days} days.{C_RESET}"
        )

    indexed = get_indexed_history()
    lines = [
        f"{C_BOLD}=== OVERDUE & HISTORY GRAVEYARD (Retention: {retention_days} days) ==={C_RESET}"
    ]

    current_date = None
    for h_tag, d_str, t in indexed:
        if d_str != current_date:
            current_date = d_str
            try:
                d_dt = datetime.strptime(d_str, "%Y-%m-%d").date()
                days_ago = (today_dt - d_dt).days
                day_num = d_dt.day
            except Exception:
                days_ago = 1
                day_num = d_str.split("-")[-1]

            if days_ago == 1:
                header_label = f"Yesterday ({d_str}) — Day {day_num}"
            else:
                header_label = f"{days_ago} days ago ({d_str}) — Day {day_num}"

            lines.append("")
            lines.append(f"{C_B_YELLOW}📅 {header_label}:{C_RESET}")

        due_info = f" {C_DIM}(due {t['due_time']}){C_RESET}" if t.get("due_time") else ""
        dur_info = f" {C_DIM}[{t['duration_minutes']}m]{C_RESET}" if t.get("duration_minutes") else ""
        lines.append(f"  {C_CYAN}[{h_tag}]{C_RESET} {C_B_RED}#{t['id']}{C_RESET} {t['title']}{due_info}{dur_info} {C_INV_RED} OVERDUE {C_RESET}")

        subtasks = t.get("subtasks", [])
        if subtasks:
            for idx, s in enumerate(subtasks):
                is_last = (idx == len(subtasks) - 1)
                branch = "└── " if is_last else "├── "
                glyph = f"{C_GREEN}[✓]{C_RESET}" if s.get("done") else f"{C_RED}[○]{C_RESET}"
                lines.append(f"      {C_GRAY}{branch}{C_RESET}{glyph} {s['id']} {s['title']}")

    yesterday_day = (today_dt - timedelta(days=1)).day
    lines.append("")
    lines.append(f"{C_DIM}How to resurrect tasks into today's active list:{C_RESET}")
    lines.append(f"  {C_CYAN}revive <day> <id>{C_RESET}  e.g. {C_WHITE}revive {yesterday_day} 1{C_RESET} (revives #1 from Day {yesterday_day})")
    lines.append(f"  {C_CYAN}revive H<num>{C_RESET}     e.g. {C_WHITE}revive H1{C_RESET} (revives using unique history tag)")
    lines.append(f"  {C_CYAN}revive <id>{C_RESET}        e.g. {C_WHITE}revive 1{C_RESET} (resolves if ID is unique across dates)")

    return "\n".join(lines)

def cli_revive(args):
    """
    Syntax:
      revive <day> <id>       e.g. revive 18 1 (revives task #1 from Day 18)
      revive H<num>           e.g. revive H1 (revives using unique history tag)
      revive yesterday <id>   e.g. revive yesterday 1
      revive <id>             e.g. revive 1 (resolves if unique across dates)
    Appends revived task to today's active list with next sequential integer ID.
    """
    if not args:
        return (
            f"{C_RED}Error: Revive target required.{C_RESET}\n"
            f"Usage:\n"
            f"  {C_CYAN}revive <day> <id>{C_RESET}       (e.g. revive 18 1)\n"
            f"  {C_CYAN}revive H<index>{C_RESET}        (e.g. revive H1)\n"
            f"  {C_CYAN}revive yesterday <id>{C_RESET}  (e.g. revive yesterday 1)\n"
            f"  {C_CYAN}revive <id>{C_RESET}            (e.g. revive 1)"
        )

    enforce_day_rollover()
    history = get_history_todos()
    indexed = get_indexed_history()

    if not indexed:
        return f"{C_GRAY}History is currently empty. No overdue tasks to revive.{C_RESET}"

    target_match = None  # (h_tag, date_str, task_dict)

    # Case 1: H-Tag (e.g. 'H1', 'h2')
    if len(args) == 1 and args[0].upper().startswith("H") and args[0][1:].isdigit():
        req_h = args[0].upper()
        for h_tag, d_str, t in indexed:
            if h_tag == req_h:
                target_match = (h_tag, d_str, t)
                break
        if not target_match:
            return f"{C_RED}Error: History tag '{req_h}' not found. Type 'history' to view tags.{C_RESET}"

    # Case 2: Date + ID (e.g. 'revive 18 1' or 'revive yesterday 1')
    elif len(args) >= 2:
        day_tok = args[0].lower().strip()
        id_tok = args[1].strip()

        if day_tok.isdigit():
            req_day = int(day_tok)
            for h_tag, d_str, t in indexed:
                try:
                    d_day = int(d_str.split("-")[2])
                except Exception:
                    continue
                if d_day == req_day and str(t.get("id")) == id_tok:
                    target_match = (h_tag, d_str, t)
                    break
            if not target_match:
                return f"{C_RED}Error: No task with ID #{id_tok} found for Day {req_day}. Type 'history' to inspect.{C_RESET}"

        elif day_tok in ("yesterday", "y"):
            today = get_local_date_str()
            try:
                today_dt = datetime.strptime(today, "%Y-%m-%d").date()
                yesterday_str = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                yesterday_str = ""
            for h_tag, d_str, t in indexed:
                if d_str == yesterday_str and str(t.get("id")) == id_tok:
                    target_match = (h_tag, d_str, t)
                    break
            if not target_match:
                return f"{C_RED}Error: No task with ID #{id_tok} found for Yesterday. Type 'history' to inspect.{C_RESET}"

        else:
            for h_tag, d_str, t in indexed:
                if d_str == day_tok and str(t.get("id")) == id_tok:
                    target_match = (h_tag, d_str, t)
                    break
            if not target_match:
                return f"{C_RED}Error: No task with ID #{id_tok} found for date '{day_tok}'. Type 'history' to inspect.{C_RESET}"

    # Case 3: Plain ID (e.g. 'revive 1')
    elif len(args) == 1:
        req_id = args[0].strip()
        matches = [(h_tag, d_str, t) for h_tag, d_str, t in indexed if str(t.get("id")) == req_id]
        if len(matches) == 1:
            target_match = matches[0]
        elif len(matches) > 1:
            lines = [
                f"{C_YELLOW}[!] Ambiguous Task ID #{req_id} found on multiple dates:{C_RESET}"
            ]
            for h_tag, d_str, t in matches:
                try:
                    day_num = int(d_str.split("-")[2])
                except Exception:
                    day_num = d_str
                lines.append(f"  {C_CYAN}[{h_tag}]{C_RESET} Day {day_num} ({d_str}): {t.get('title')}")
            lines.append("")
            lines.append(f"Please specify the day number: {C_WHITE}revive <day> {req_id}{C_RESET} (e.g. {C_WHITE}revive {matches[0][1].split('-')[2]} {req_id}{C_RESET}) or {C_WHITE}revive {matches[0][0]}{C_RESET}")
            return "\n".join(lines)
        else:
            return f"{C_RED}Error: Task ID #{req_id} not found in history. Type 'history' to view overdue tasks.{C_RESET}"

    if not target_match:
        return f"{C_RED}Error: Unable to resolve revive target. Type 'history' for list.{C_RESET}"

    h_tag, date_str, task_data = target_match

    # 1. Remove from history
    if date_str in history:
        history[date_str] = [t for t in history[date_str] if t.get("uuid") != task_data.get("uuid") and str(t.get("id")) != str(task_data.get("id"))]
        if not history[date_str]:
            del history[date_str]
        save_history_todos(history)

    # 2. Append to active todos with next sequential integer ID
    todos = get_local_todos()
    today = get_local_date_str()
    num_ids = [int(t["id"]) for t in todos if str(t.get("id", "")).isdigit()]
    next_id = str(max(num_ids) + 1) if num_ids else "1"

    orig_id = task_data.get("id")
    orig_title = task_data.get("title", "")

    revived_task = dict(task_data)
    revived_task["id"] = next_id
    revived_task["uuid"] = str(uuid.uuid4())
    revived_task["task_date"] = today
    revived_task["done"] = False
    revived_task["updated_at"] = datetime.now(timezone.utc).isoformat()
    revived_task["synced"] = False

    # Remap subtask IDs to new parent ID and reset completion
    subtasks = revived_task.get("subtasks", [])
    if isinstance(subtasks, list):
        for idx, s in enumerate(subtasks):
            if isinstance(s, dict):
                s["id"] = f"{next_id}.{idx + 1}"
                s["done"] = False

    todos.append(revived_task)
    save_local_todos(todos)

    try:
        window.PyTodoBridge.playSound("revive")
    except Exception:
        pass
    try:
        window.PyTodoBridge.triggerBackgroundSync()
    except Exception:
        pass

    return (
        f"{C_B_GREEN}✨ Resurrected task to today's active list:{C_RESET}\n"
        f"  {C_BOLD}#{next_id}{C_RESET} {orig_title} {C_DIM}(formerly [{h_tag}] #{orig_id} from {date_str}){C_RESET}\n"
        f"{C_DIM}Task is now active for today. Type 'ls' to view.{C_RESET}"
    )

def cli_streak(args):
    """
    Syntax: streak
    Displays the Discipline Streak Engine telemetry:
    - Current consecutive days with 100% completion
    - All-time high record
    - Today's intraday progress toward midnight
    - 7-day completion history ledger
    """
    enforce_day_rollover()
    streak_data = get_streak_data()
    cur = streak_data.get("current_streak", 0)
    ath = streak_data.get("highest_streak", 0)
    today = get_local_date_str()

    if cur > 0 and cur >= ath:
        try:
            window.PyTodoBridge.playSound("streak")
        except Exception:
            pass

    todos = get_local_todos()
    today_todos = [t for t in todos if (t.get("task_date") or t.get("date") or today) == today]
    total_today = len(today_todos)
    done_today = sum(1 for t in today_todos if t.get("done"))

    lines = [
        f"{C_BOLD}{C_ORANGE}🔥 DISCIPLINE STREAK ENGINE 🔥{C_RESET}",
        f"{C_GRAY}===================================================={C_RESET}",
        f"  {C_BOLD}Current Streak:{C_RESET}      {C_B_YELLOW}🔥 {cur} Day{'s' if cur != 1 else ''}{C_RESET}",
        f"  {C_BOLD}All-Time High (ATH):{C_RESET} {C_B_GREEN}🏆 {ath} Day{'s' if ath != 1 else ''}{C_RESET}",
        ""
    ]

    if total_today == 0:
        lines.append(f"  {C_BOLD}Today's Status:{C_RESET}      {C_GRAY}[○ 0 tasks scheduled for today]{C_RESET}")
    elif done_today == total_today:
        lines.append(f"  {C_BOLD}Today's Status:{C_RESET}      {C_B_GREEN}[✔ 100% Complete ({done_today}/{total_today}) — Streak +1 Solidifies at Midnight!]{C_RESET}")
    else:
        rem = total_today - done_today
        lines.append(f"  {C_BOLD}Today's Status:{C_RESET}      {C_YELLOW}[◐ {done_today}/{total_today} Done — {rem} task{'s' if rem != 1 else ''} remaining before midnight]{C_RESET}")

    lines.append("")
    lines.append(f"{C_BOLD}Recent 7-Day Completion Ledger:{C_RESET}")
    history_log = streak_data.get("history_log", {})
    try:
        today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    except Exception:
        today_dt = get_local_now().date()

    has_log_entries = False
    for i in range(1, 8):
        past_date = (today_dt - timedelta(days=i)).strftime("%Y-%m-%d")
        if past_date in history_log:
            has_log_entries = True
            rec = history_log[past_date]
            tot = rec.get("total", 0)
            dn = rec.get("done", 0)
            pct = int(round((dn / tot * 100))) if tot > 0 else 0
            if rec.get("success"):
                badge = f"{C_B_GREEN}[✔ PASS]{C_RESET} {pct}% ({dn}/{tot}) {C_B_GREEN}Streak Extended{C_RESET}"
            else:
                badge = f"{C_B_RED}[✘ FAIL]{C_RESET} {pct}% ({dn}/{tot}) {C_RED}Streak Reset{C_RESET}"
            lines.append(f"  {past_date}: {badge}")

    if not has_log_entries:
        lines.append(f"  {C_GRAY}(No historical days logged yet. Complete today's tasks to begin!){C_RESET}")

    lines.append("")
    lines.append(f"{C_DIM}Rule: Complete 100% of your tasks before 23:59:59 each day to keep your streak alive.{C_RESET}")
    lines.append(f"{C_DIM}Any uncompleted tasks at midnight reset the streak to 0.{C_RESET}")
    return "\n".join(lines)

def cli_theme(args):
    """
    Syntax: theme [name]
    Select or switch terminal visual theme.
    Available: classic, matrix, cyberpunk, dracula, nord, monokai, solarized.
    """
    available = ["classic", "matrix", "cyberpunk", "dracula", "nord", "monokai", "solarized"]
    if not args:
        try:
            curr = str(window.PyTodoBridge.getTheme()).lower()
        except Exception:
            curr = "classic"

        lines = [
            f"{C_BOLD}PyTodo Terminal Color Themes:{C_RESET}"
        ]
        for th in available:
            if th == curr:
                indicator = f"{C_B_GREEN}● [ACTIVE]{C_RESET}"
            else:
                indicator = f"{C_GRAY}○{C_RESET}         "
            lines.append(f"  {indicator} {C_CYAN}{th:<12}{C_RESET}")

        lines.append("")
        lines.append(f"{C_DIM}Switch theme: theme <name> (e.g. theme matrix, theme dracula, theme cyberpunk){C_RESET}")
        return "\n".join(lines)

    target = args[0].lower().strip()
    if target not in available:
        return f"{C_RED}Error: Unknown theme '{target}'. Available themes: {', '.join(available)}{C_RESET}"

    try:
        applied = str(window.PyTodoBridge.setTheme(target))
        try:
            window.PyTodoBridge.playSound("theme")
        except Exception:
            pass
        return f"{C_B_GREEN}[✔] Theme switched to '{applied}'. Saved to preferences.{C_RESET}"
    except Exception as e:
        return f"{C_RED}Error applying theme: {str(e)}{C_RESET}"

def cli_config(args):
    """
    Syntax: config [key] [value]
    Manages user and terminal configuration.
    Keys:
      retention <1-7>        (Retention window in days for overdue tasks)
      focus.step [duration]  (Timer increment/decrement step for focus mode)
      theme <name>           (Select terminal theme)
    """
    if not args:
        try:
            step_sec = int(window.PyTodoBridge.getFocusStep())
        except Exception:
            step_sec = 300
        mins = step_sec // 60
        secs = step_sec % 60
        step_fmt = f"{mins}m" if not secs else (f"{mins}m {secs}s" if mins else f"{secs}s")
        ret_days = get_retention_days()
        try:
            curr_theme = str(window.PyTodoBridge.getTheme())
        except Exception:
            curr_theme = "classic"
        try:
            snd = "on" if window.PyTodoBridge.isSoundEnabled() else "off"
        except Exception:
            snd = "on"

        lines = [
            f"{C_BOLD}PyTodo Configuration:{C_RESET}",
            f"  {C_CYAN}retention{C_RESET}   = {C_WHITE}{ret_days} days{C_RESET} (range: 1 - 7 days)",
            f"  {C_CYAN}theme{C_RESET}       = {C_WHITE}{curr_theme}{C_RESET}",
            f"  {C_CYAN}focus.step{C_RESET}  = {C_WHITE}{step_fmt}{C_RESET} ({step_sec}s)",
            f"  {C_CYAN}sound{C_RESET}       = {C_WHITE}{snd}{C_RESET}",
            "",
            f"{C_DIM}Usage: config <key> <val> (e.g. config retention 7, config theme matrix){C_RESET}"
        ]
        return "\n".join(lines)

    key = args[0].lower().strip()
    subargs = args[1:]

    if key in ("retention", "retention_days", "retention.days"):
        if not subargs:
            return f"{C_CYAN}[i] Current overdue retention window:{C_RESET} {get_retention_days()} days"
        try:
            val = int(subargs[0])
            if val < 1 or val > 7:
                return f"{C_RED}Error: Retention window must be between 1 and 7 days.{C_RESET}"
            set_retention_days(val)
            today = get_local_date_str()
            history = get_history_todos()
            cleaned, pruned = prune_history_retention(history, val, today)
            save_history_todos(cleaned)
            prune_msg = f" (pruned {pruned} older tasks)" if pruned > 0 else ""
            return f"{C_GREEN}[✔] Overdue retention window set to {val} days{prune_msg}.{C_RESET}"
        except ValueError:
            return f"{C_RED}Error: Invalid retention day count '{subargs[0]}'. Must be integer 1-7.{C_RESET}"

    elif key in ("focus.step", "focus_step", "step"):
        return handle_focus_step_command(subargs)

    elif key in ("theme", "color"):
        return cli_theme(subargs)

    elif key in ("sound", "audio"):
        return cli_sound(subargs)

    else:
        return f"{C_RED}Error: Unknown config key '{key}'. Available keys: retention, theme, focus.step, sound{C_RESET}"

def cli_focus(args):
    """
    Syntax: focus <id> [-time <dur>] [duration] [-full]
            focus step [duration]
    Launches an interactive Pomodoro focus session with visual percentage bar.
    Examples:
      focus 1 -time 42m
      focus 1 25m
      focus 1.1 15m -full
      focus 1 1 -time 42m
      focus step 10m
    """
    if not args:
        return f"{C_RED}Error: Task or subtask ID required. Usage: focus <id> [-time <dur>] [duration] [-full]{C_RESET}"

    # Check for subcommand: focus step [dur] or focus config [dur]
    if args[0].lower() in ("step", "config"):
        return handle_focus_step_command(args[1:])

    is_fullscreen = False
    dur_flag_val = None
    positional = []

    idx = 0
    while idx < len(args):
        a = args[idx]
        a_lower = a.lower()
        if a_lower in ("-full", "--full", "-f"):
            is_fullscreen = True
            idx += 1
        elif a_lower in ("-time", "--time", "-t"):
            if idx + 1 < len(args):
                dur_flag_val = args[idx + 1]
                idx += 2
            else:
                return f"{C_RED}Error: Flag '{a}' requires a duration value (e.g. -time 42m).{C_RESET}"
        elif a_lower.startswith("-time=") or a_lower.startswith("--time="):
            dur_flag_val = a.split("=", 1)[1]
            idx += 1
        elif a_lower.startswith("-t=") or a_lower.startswith("-t:"):
            dur_flag_val = a[3:]
            idx += 1
        else:
            positional.append(a)
            idx += 1

    if not positional:
        return f"{C_RED}Error: Task ID required. Usage: focus <id> [-time <dur>] [duration] [-full]{C_RESET}"

    # Handle space notation:
    # If first two positional tokens are digits and first is not dotted:
    # e.g., positional = ['1', '1'] or ['1', '1', '25m']
    dur_pos_val = None
    if len(positional) >= 2 and positional[0].isdigit() and positional[1].isdigit() and "." not in positional[0]:
        target_id = f"{positional[0]}.{positional[1]}"
        if len(positional) > 2:
            dur_pos_val = positional[2]
    else:
        target_id = positional[0].strip()
        if len(positional) > 1:
            dur_pos_val = positional[1]

    chosen_dur_str = dur_flag_val if dur_flag_val is not None else dur_pos_val

    todos = get_local_todos()
    target_task = None
    parent_title = ""
    target_title = ""
    sub_dur_min = None

    if "." in target_id:
        parent_id, _ = target_id.split(".", 1)
        for t in todos:
            if t["id"] == parent_id or t.get("uuid") == parent_id:
                for s in t.get("subtasks", []):
                    if s["id"] == target_id:
                        target_task = t
                        parent_title = t["title"]
                        target_title = s["title"]
                        sub_dur_min = s.get("duration_minutes")
                        break
    else:
        for t in todos:
            if t["id"] == target_id or t.get("uuid") == target_id:
                target_task = t
                target_title = t["title"]
                break

    if not target_task:
        return f"{C_RED}Error: Task or subtask '{target_id}' not found.{C_RESET}"

    if chosen_dur_str:
        sec = parse_duration_seconds(chosen_dur_str)
        if not sec or sec <= 0:
            return f"{C_RED}Error: Invalid duration format '{chosen_dur_str}'. Use 42m, 25m, 1h, 1h30m, 90s.{C_RESET}"
        if sec > 86400:
            return f"{C_RED}Error: Maximum focus session duration is 24h (1440m).{C_RESET}"
        duration_sec = sec
    elif sub_dur_min:
        duration_sec = sub_dur_min * 60
    elif target_task.get("duration_minutes"):
        duration_sec = target_task["duration_minutes"] * 60
    else:
        duration_sec = 25 * 60

    duration_min = max(1, round(duration_sec / 60))

    try:
        payload = json.dumps({
            "id": target_id,
            "title": target_title,
            "parent_title": parent_title,
            "duration_sec": duration_sec,
            "is_fullscreen": is_fullscreen
        })
        window.PyTodoBridge.enterFocusMode(payload)
        return ""
    except Exception as e:
        return f"Focus session starting for [{target_id}] ({duration_min}m)..."

def cli_subtask(args):
    """
    Syntax: subtask <id> <subtask_title> (or subtask add <id> <title> or add-sub)
    Convenience shortcut to append a subtask directly.
    """
    if len(args) >= 3 and args[0].lower() in ("add", "new"):
        task_id = args[1]
        sub_title = " ".join(args[2:])
    elif len(args) >= 2:
        task_id = args[0]
        sub_title = " ".join(args[1:])
    else:
        return f"{C_RED}Error: Usage: subtask <id> <subtask_title> (e.g. subtask 1 Review PR){C_RESET}"
    return cli_edit([task_id, "--add-sub", sub_title])

def cli_rm(args):
    """
    Syntax: rm <id> (or del / delete)
    Deletes a task or subtask by ID.
    """
    if not args:
        return f"{C_RED}Error: Task or subtask ID required. Usage: rm <id>{C_RESET}"
    target_id = args[0].strip()
    todos = get_local_todos()

    # Case A: Remove subtask
    if "." in target_id:
        parent_id, _ = target_id.split(".", 1)
        for t in todos:
            if t["id"] == parent_id or t.get("uuid") == parent_id:
                subtasks = t.get("subtasks", [])
                for idx, s in enumerate(subtasks):
                    if s["id"] == target_id:
                        removed = subtasks.pop(idx)
                        # Stable Monotonic IDs: do NOT renumber remaining subtasks
                        if len(subtasks) > 0 and all(item.get("done") for item in subtasks if isinstance(item, dict)):
                            t["done"] = True
                        t["updated_at"] = datetime.now(timezone.utc).isoformat()
                        t["synced"] = False
                        save_local_todos(todos)
                        try:
                            window.PyTodoBridge.playSound("rm")
                        except Exception:
                            pass
                        try:
                            window.PyTodoBridge.triggerBackgroundSync()
                        except Exception:
                            pass
                        return f"{C_YELLOW}[-] Subtask removed:{C_RESET} [{target_id}] {removed['title']}"
        return f"{C_RED}Error: Subtask '{target_id}' not found.{C_RESET}"

    # Case B: Remove parent task
    for idx, t in enumerate(todos):
        if t["id"] == target_id or t.get("uuid") == target_id:
            removed = todos.pop(idx)
            t_uuid = removed.get("uuid") or str(removed.get("id"))
            add_tombstone(t_uuid)
            save_local_todos(todos)
            try:
                window.PyTodoBridge.playSound("rm")
            except Exception:
                pass
            try:
                window.PyTodoBridge.triggerBackgroundSync()
            except Exception:
                pass
            return f"{C_YELLOW}[-] Task deleted:{C_RESET} [{target_id}] {removed['title']}"

    return f"{C_RED}Error: Task ID '{target_id}' not found.{C_RESET}"

# 6. Bridge APIs for JavaScript (HTOP Frame, Prompt Stats, Autocomplete)
def get_dashboard_frame() -> str:
    """Renders a single frame of the live HTOP dashboard monitor."""
    purge_expired_tasks()
    todos = get_local_todos()
    now = get_local_now()

    # 1. Day Elapsed Progress Bar
    sec_today = now.hour * 3600 + now.minute * 60 + now.second
    day_pct = min(100.0, (sec_today / 86400.0) * 100.0)
    sec_left = 86400 - sec_today
    h_left = sec_left // 3600
    m_left = (sec_left % 3600) // 60
    s_left = sec_left % 60

    term_width = get_terminal_width()
    separator_len = max(20, min(term_width, 160))

    total_cnt = len(todos)
    done_cnt = sum(1 for t in todos if t.get("done"))
    task_pct = (done_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0

    if term_width >= 80:
        bar_width = min(30, max(10, term_width - 52))
        filled_day = int((day_pct / 100.0) * bar_width)
        day_bar = f"{C_YELLOW}" + ("=" * filled_day) + ">" + ("." * max(0, bar_width - filled_day - 1)) + f"{C_RESET}"
        filled_task = int((task_pct / 100.0) * bar_width)
        task_bar = f"{C_GREEN}" + ("=" * filled_task) + ">" + ("." * max(0, bar_width - filled_task - 1)) + f"{C_RESET}"
        day_line = f"Day Progress:  [{day_bar}] {day_pct:5.1f}% ({h_left:02d}h {m_left:02d}m {s_left:02d}s to Midnight)"
        task_line = f"Task Progress: [{task_bar}] {task_pct:5.1f}% ({done_cnt}/{total_cnt} tasks completed)"
    elif term_width >= 55:
        bar_width = max(8, min(20, term_width - 38))
        filled_day = int((day_pct / 100.0) * bar_width)
        day_bar = f"{C_YELLOW}" + ("=" * filled_day) + ">" + ("." * max(0, bar_width - filled_day - 1)) + f"{C_RESET}"
        filled_task = int((task_pct / 100.0) * bar_width)
        task_bar = f"{C_GREEN}" + ("=" * filled_task) + ">" + ("." * max(0, bar_width - filled_task - 1)) + f"{C_RESET}"
        day_line = f"Day:  [{day_bar}] {day_pct:4.0f}% ({h_left:02d}h{m_left:02d}m left)"
        task_line = f"Task: [{task_bar}] {task_pct:4.0f}% ({done_cnt}/{total_cnt} done)"
    else:
        bar_width = max(4, min(10, term_width - 24))
        filled_day = int((day_pct / 100.0) * bar_width)
        day_bar = f"{C_YELLOW}" + ("=" * filled_day) + ">" + ("." * max(0, bar_width - filled_day - 1)) + f"{C_RESET}"
        filled_task = int((task_pct / 100.0) * bar_width)
        task_bar = f"{C_GREEN}" + ("=" * filled_task) + ">" + ("." * max(0, bar_width - filled_task - 1)) + f"{C_RESET}"
        if term_width < 34:
            day_line = f"Day:  [{day_bar}] {day_pct:3.0f}%"
            task_line = f"Task: [{task_bar}] {task_pct:3.0f}%"
        else:
            day_line = f"Day:  [{day_bar}] {day_pct:3.0f}% ({h_left}h left)"
            task_line = f"Task: [{task_bar}] {task_pct:3.0f}% ({done_cnt}/{total_cnt})"

    title_hdr = f"{C_B_WHITE}=== PYTODO LIVE HTOP MONITOR ==={C_RESET}" if term_width >= 40 else f"{C_B_WHITE}=== PYTODO HTOP ==={C_RESET}"
    time_hdr = f"Local Time:    {now.strftime('%Y-%m-%d %H:%M:%S')}" if term_width >= 40 else f"Time: {now.strftime('%H:%M:%S')}"

    if term_width >= 80:
        table_hdr = f"{C_BOLD}ID    DUE IN / HEATMAP        STATUS    TASK{C_RESET}"
    elif term_width >= 60:
        table_hdr = f"{C_BOLD}ID    DUE / HEATMAP  STATUS  TASK{C_RESET}"
    else:
        table_hdr = f"{C_BOLD}ID   STATUS  TASK{C_RESET}"

    lines = [
        title_hdr,
        time_hdr,
        day_line,
        task_line,
        "",
        table_hdr,
        f"{C_GRAY}" + ("-" * separator_len) + f"{C_RESET}"
    ]

    if not todos:
        lines.append(f"{C_GRAY}(No tasks scheduled for today){C_RESET}")
    else:
        for t in todos:
            _, tag, color = get_deadline_info(t)
            st = f"{C_GREEN}[DONE]{C_RESET}" if t["done"] else f"{C_RED}[TODO]{C_RESET}"

            subtasks = t.get("subtasks", [])
            sub_progress = ""
            if subtasks:
                sub_done_cnt = sum(1 for s in subtasks if s.get("done"))
                if term_width < 85:
                    sub_progress = f" {C_DIM}[{sub_done_cnt}/{len(subtasks)}]{C_RESET}"
                else:
                    sub_progress = f" {C_DIM}[{sub_done_cnt}/{len(subtasks)} done]{C_RESET}"

            dur_tag = f" {C_DIM}({t['duration_minutes']}m){C_RESET}" if t.get("duration_minutes") else ""

            if term_width >= 80:
                badge = f"{color}{pad_string(tag, 22)}{C_RESET}"
                prefix_fmt = f"{C_CYAN}{t['id']:<4}{C_RESET}  {badge}  {st}   "
                prefix_w = 4 + 2 + 22 + 2 + 6 + 3
            elif term_width >= 60:
                badge = f"{color}{pad_string(tag, 12)}{C_RESET}"
                prefix_fmt = f"{C_CYAN}{t['id']:<4}{C_RESET}  {badge}  {st}  "
                prefix_w = 4 + 2 + 12 + 2 + 6 + 2
            else:
                prefix_fmt = f"{C_CYAN}{t['id']:<4}{C_RESET} {st}  "
                prefix_w = 4 + 1 + 6 + 2

            suffix_w = get_visual_width(dur_tag) + get_visual_width(sub_progress)
            if term_width - prefix_w - suffix_w < 4:
                dur_tag = ""
                suffix_w = get_visual_width(sub_progress)
                if term_width - prefix_w - suffix_w < 4:
                    sub_progress = ""
                    suffix_w = 0

            avail_title = max(2, term_width - prefix_w - suffix_w)
            safe_title = truncate_visual(t['title'], avail_title)
            if t["done"]:
                title = f"{C_GRAY}\x1b[9m{safe_title}\x1b[29m\x1b[0m"
            else:
                title = safe_title
            lines.append(f"{prefix_fmt}{title}{dur_tag}{sub_progress}")

            # Option C: Nested Subtask Hierarchy aligned inside TASK column for HTOP
            if subtasks:
                if term_width >= 95:
                    indent = " " * 44
                elif term_width >= 80:
                    indent = " " * 40
                elif term_width >= 60:
                    indent = " " * 30
                else:
                    indent = "    "

                for idx, sub in enumerate(subtasks):
                    is_last = (idx == len(subtasks) - 1)
                    branch = "└── " if is_last else "├── "
                    sub_done = bool(sub.get("done"))

                    glyph = f"{C_GREEN}[✓]{C_RESET}" if sub_done else f"{C_AMBER}[○]{C_RESET}"
                    sub_id = f"{C_CYAN}{sub['id']:<4}{C_RESET}"

                    prefix_w = get_visual_width(f"{indent}{branch}[✓] {sub['id']:<4} ")
                    avail_title = max(2, term_width - prefix_w)

                    raw_title = sub.get("title", "")
                    safe_title = truncate_visual(raw_title, avail_title)
                    if sub_done:
                        styled_title = f"{C_GRAY}\x1b[9m{safe_title}\x1b[29m\x1b[0m"
                    else:
                        styled_title = f"{C_WHITE}{safe_title}{C_RESET}"

                    lines.append(f"{indent}{C_GRAY}{branch}{C_RESET}{glyph} {sub_id} {styled_title}")

    lines.append("")
    if term_width >= 55:
        lines.append(f"{C_DIM}Press 'q' or 'Esc' to exit dashboard | Refreshing every 1s{C_RESET}")
    else:
        lines.append(f"{C_DIM}'q'/Esc: exit | 1s refresh{C_RESET}")
    return "\r\n".join(lines)

def get_prompt_stats() -> str:
    """Returns JSON payload with telemetry data for the live terminal prompt."""
    todos = get_local_todos()
    now = get_local_now()
    sec_left = 86400 - (now.hour * 3600 + now.minute * 60 + now.second)
    h = max(0, sec_left // 3600)
    m = max(0, (sec_left % 3600) // 60)
    s = max(0, sec_left % 60)

    done_cnt = sum(1 for t in todos if t.get("done"))
    total_cnt = len(todos)

    return json.dumps({
        "today_date": get_local_date_str(),
        "countdown_str": f"{h:02d}h {m:02d}m {s:02d}s",
        "done_count": done_cnt,
        "total_count": total_cnt,
        "pairing_code": get_pairing_code() or ""
    })

def get_autocomplete_suggestions(current_line: str) -> str:
    """Returns JSON array of autocompletion suggestions matching the active command line."""
    has_trailing_space = current_line.endswith(" ")
    trimmed = current_line.strip()
    todos = get_local_todos()
    verbs = [
        "add", "ls", "done", "undone", "focus", "edit", "subtask", "add-sub",
        "rm", "delete", "history", "overdue", "revive", "rv", "streak",
        "theme", "top", "watch", "link", "unlink", "code", "sync", "sound", "config", "export", "import", "help", "clear"
    ]

    if not trimmed:
        return json.dumps(verbs)

    tokens = trimmed.split()
    if len(tokens) == 1 and not has_trailing_space:
        prefix = tokens[0].lower()
        matches = [v for v in verbs if v.startswith(prefix)]
        return json.dumps(matches)

    verb = tokens[0].lower()
    last_token = "" if has_trailing_space else tokens[-1]

    if verb == "config":
        keys = ["retention", "theme", "focus.step", "sound"]
        matches = [k for k in keys if k.startswith(last_token)]
        return json.dumps(matches)

    if verb in ("theme", "colors", "themes"):
        theme_names = ["classic", "matrix", "cyberpunk", "dracula", "nord", "monokai", "solarized"]
        matches = [th for th in theme_names if th.startswith(last_token)]
        return json.dumps(matches)

    if verb in ("revive", "rv"):
        indexed = get_indexed_history()
        candidates = []
        for h_tag, d_str, t in indexed:
            candidates.append(h_tag)
            try:
                candidates.append(str(int(d_str.split("-")[2])))
            except Exception:
                pass
            candidates.append(str(t.get("id")))
        # Deduplicate candidates preserving order
        unique_c = []
        for c in candidates:
            if c not in unique_c:
                unique_c.append(c)
        matches = [c for c in unique_c if c.lower().startswith(last_token.lower())]
        return json.dumps(matches)

    # Task ID & Subtask ID completion for 'done', 'undone', 'focus', 'edit', 'subtask', 'add-sub', 'rm', 'delete', and aliases
    if verb in ("done", "undone", "focus", "edit", "subtask", "add-sub", "rm", "delete", "d", "u", "f", "e", "s"):
        candidates = []
        if verb in ("focus", "f"):
            candidates.append("step")
        for t in todos:
            candidates.append(t["id"])
            for s in t.get("subtasks", []):
                candidates.append(s["id"])
        matches = [c for c in candidates if c.startswith(last_token)]
        return json.dumps(matches)

    return json.dumps([])

def cli_export(args):
    """
    Syntax: export [pretty]
    Exports all tasks, subtasks, overdue history, streak records, and settings to JSON.
    Triggers browser file download or returns JSON.
    """
    todos = get_local_todos()
    history = get_history_todos()
    streak = get_streak_data()
    retention = get_retention_days()
    theme = "classic"
    try:
        theme = str(window.PyTodoBridge.getTheme()).lower()
    except Exception:
        pass

    payload = {
        "version": "2.2.5",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "pairing_code": get_pairing_code() or "",
        "todos": todos,
        "history": history,
        "streak": streak,
        "config": {
            "retention_days": retention,
            "theme": theme
        }
    }
    dumped = json.dumps(payload, indent=2)
    filename = f"pytodo_backup_{get_local_date_str()}.json"
    downloaded = False
    is_raw = any(a.lower() in ("json", "--raw", "--json", "-j") for a in (args or []))
    if not is_raw:
        try:
            if hasattr(window, "PyTodoBridge") and hasattr(window.PyTodoBridge, "downloadJSON"):
                window.PyTodoBridge.downloadJSON(filename, dumped)
                downloaded = True
        except Exception:
            pass

    if downloaded:
        total_hist = sum(len(v) for v in history.values()) if isinstance(history, dict) else 0
        return (
            f"{C_GREEN}[✔] Backup exported successfully:{C_RESET} {C_CYAN}{filename}{C_RESET}\n"
            f"{C_GRAY}Contains {len(todos)} active tasks and {total_hist} history tasks.{C_RESET}"
        )
    return dumped

def cli_import(args):
    """
    Syntax: import <json_string> (or import merge <json_string> / import replace <json_string>)
    Restores tasks, history, and streak from JSON backup.
    """
    if not args:
        return f"{C_RED}Error: JSON backup data required. Usage: import <json_string> or import merge/replace <json_string>{C_RESET}"

    mode = "merge"
    raw_str = " ".join(args)
    if args[0].lower() in ("merge", "--merge"):
        mode = "merge"
        raw_str = " ".join(args[1:])
    elif args[0].lower() in ("replace", "--replace", "overwrite"):
        mode = "replace"
        raw_str = " ".join(args[1:])

    try:
        data = json.loads(raw_str)
    except Exception as e:
        return f"{C_RED}Error: Malformed JSON: {e}{C_RESET}"

    if not isinstance(data, dict):
        return f"{C_RED}Error: Invalid backup format. Root must be a JSON object.{C_RESET}"

    new_todos = data.get("todos", [])
    if not isinstance(new_todos, list):
        return f"{C_RED}Error: Backup 'todos' field must be an array.{C_RESET}"

    # Clean and sanitize incoming tasks
    cleaned_todos = []
    now_iso = datetime.now(timezone.utc).isoformat()
    today_str = get_local_date_str()
    for t in new_todos:
        if not isinstance(t, dict):
            continue
        title = sanitize_text(t.get("title", ""))
        if not title:
            continue
        c_subs = []
        for s in t.get("subtasks", []):
            if isinstance(s, dict):
                stitle = sanitize_text(s.get("title", ""))
                if stitle:
                    c_subs.append({
                        "id": str(s.get("id", "")),
                        "title": stitle,
                        "done": bool(s.get("done", False)),
                        "updated_at": str(s.get("updated_at") or now_iso)
                    })
        cleaned_todos.append({
            "id": str(t.get("id", "")),
            "uuid": str(t.get("uuid") or uuid.uuid4()),
            "pairing_code": get_pairing_code() or "",
            "task_date": str(t.get("task_date") or today_str),
            "title": title,
            "due_time": parse_due_time(str(t.get("due_time", ""))) if t.get("due_time") else None,
            "duration_minutes": parse_duration(str(t.get("duration_minutes", ""))) if t.get("duration_minutes") else None,
            "done": bool(t.get("done", False)),
            "subtasks": c_subs,
            "created_at": str(t.get("created_at") or now_iso),
            "updated_at": str(t.get("updated_at") or now_iso),
            "synced": False
        })

    if mode == "replace":
        todos = normalize_and_migrate_todos(cleaned_todos)
    else:
        existing = get_local_todos()
        todos = normalize_and_migrate_todos(existing + cleaned_todos)

    save_local_todos(todos)

    # Optionally restore history / streak if present
    if "history" in data and isinstance(data["history"], dict):
        if mode == "replace":
            save_history_todos(data["history"])
        else:
            curr_h = get_history_todos()
            for dk, dlist in data["history"].items():
                if isinstance(dlist, list):
                    curr_h.setdefault(dk, []).extend(dlist)
            save_history_todos(curr_h)

    if "streak" in data and isinstance(data["streak"], dict) and mode == "replace":
        save_streak_data(data["streak"])

    try:
        window.PyTodoBridge.triggerBackgroundSync()
    except Exception:
        pass

    return f"{C_GREEN}[✔] Backup successfully imported ({mode} mode):{C_RESET} {len(todos)} active tasks loaded."

def check_midnight_wipe() -> int:
    """Invoked by JS clock monitor to check if a new day has arrived."""
    return purge_expired_tasks()

async def cli_pair(args):
    """
    Syntax: pair [status | new | generate | link <code> | unlink | sync]
    Unified pairing helper matching user intuition.
    """
    if not args:
        return await cli_code([])
    sub = args[0].lower()
    if sub in ("status", "info"):
        return await cli_link(["status"])
    if sub in ("new", "generate", "create"):
        return await cli_link(["generate"] + args[1:])
    if sub == "sync":
        return await cli_sync(args[1:])
    if sub == "unlink":
        return await cli_unlink([])
    if sub == "link" and len(args) > 1:
        return await cli_link(args[1:])
    return await cli_link(args)

COMMANDS = {
    # Core CLI Commands
    "add": cli_add,
    "ls": cli_ls,
    "done": cli_done,
    "undone": cli_undone,
    "focus": cli_focus,
    "edit": cli_edit,
    "subtask": cli_subtask,
    "add-sub": cli_subtask,
    "rm": cli_rm,
    "del": cli_rm,
    "delete": cli_rm,
    "history": cli_history,
    "overdue": cli_history,
    "graveyard": cli_history,
    "h-list": cli_history,
    "revive": cli_revive,
    "rv": cli_revive,
    "streak": cli_streak,
    "theme": cli_theme,
    "themes": cli_theme,
    "colors": cli_theme,
    "pair": cli_pair,
    "pairing": cli_pair,
    "link": cli_link,
    "unlink": cli_unlink,
    "code": cli_code,
    "sync": cli_sync,
    "sound": cli_sound,
    "config": cli_config,
    "export": cli_export,
    "import": cli_import,
    "top": cli_top,
    "watch": cli_top,
    "heatmap": cli_ls,
    "today": cli_ls,

    # Micro-Command Shortcuts (Single-Letter Mobile Aliases)
    "a": cli_add,
    "d": cli_done,
    "l": cli_ls,
    "u": cli_undone,
    "s": cli_subtask,
    "f": cli_focus,
    "e": cli_edit,
    "t": cli_top,
    "p": cli_pair,
    "c": lambda _: "__CLEAR_SCREEN__",
    "cls": lambda _: "__CLEAR_SCREEN__",
    "h": lambda _: COMMANDS["help"](None),

    "help": lambda _: (
        f"{C_BOLD}PyTodo Commands:{C_RESET}\n"
        f"  {C_CYAN}add (or a) <title> [by/at <time>] [for <dur>]{C_RESET} Frictionless add with auto NLP or flags\n"
        f"  {C_CYAN}ls (or l / today){C_RESET}                                List tasks (auto-adapts to mobile)\n"
        f"  {C_CYAN}done (or d) <id> (e.g. 1, 1.1){C_RESET}                   Mark task or subtask complete\n"
        f"  {C_CYAN}undone (or u) <id>{C_RESET}                               Revert task or subtask to incomplete\n"
        f"  {C_CYAN}subtask (or s) <id> <title> [by/for ...]{C_RESET}             Add subtask with optional auto NLP\n"
        f"  {C_CYAN}focus (or f) <id> [-time <dur>] [-full]{C_RESET}             Pomodoro focus (keys: + / - / Space / q)\n"
        f"  {C_CYAN}history (or overdue){C_RESET}                                View uncompleted past tasks (1-7d retention)\n"
        f"  {C_CYAN}revive <day> <id> (or revive H1){C_RESET}                   Resurrect overdue task into today's list\n"
        f"  {C_CYAN}streak{C_RESET}                                             View discipline streak & 7-day completion ledger\n"
        f"  {C_CYAN}theme [name]{C_RESET}                                       Select visual color palette (7 themes)\n"
        f"  {C_CYAN}config [key] [val]{C_RESET}                             View or set configs (retention, theme, focus.step)\n"
        f"  {C_CYAN}edit (or e) <id> [options]{C_RESET}                           Modify task, add/remove subtasks\n"
        f"  {C_CYAN}rm <id>{C_RESET}                                       Delete task or subtask\n"
        f"  {C_CYAN}top (or t) / watch [-full]{C_RESET}                           Launch live monitor (optional fullscreen)\n"
        f"  {C_CYAN}pair [status | new | link | sync]{C_RESET}                  Sync across devices with pairing key\n"
        f"  {C_CYAN}code{C_RESET}                                           Show active pairing key for other devices\n"
        f"  {C_CYAN}sync{C_RESET}                                          Force cloud push & pull\n"
        f"  {C_CYAN}sound [on | off | test]{C_RESET}                       Control 8-bit retro audio FX\n"
        f"  {C_CYAN}export [pretty]{C_RESET}                                 Export backup JSON file\n"
        f"  {C_CYAN}import [merge|replace] <json>{C_RESET}                   Restore tasks from backup JSON\n"
        f"  {C_CYAN}clear (or c){C_RESET}                                  Clear terminal screen\n"
        f"  {C_CYAN}help (or h){C_RESET}                                   Show this guide"
    )
}

async def handle_command(raw_line):
    # Synchronous pre-command rollover gatekeeper:
    # Guarantees that any past day tasks are archived and streak updated BEFORE any command executes
    enforce_day_rollover()

    trimmed = (raw_line or "").strip()
    if not trimmed:
        return ""

    # Special handling for 'import' to preserve raw JSON quotes from shlex stripping
    if trimmed.startswith("import"):
        parts = trimmed.split(None, 1)
        verb = "import"
        args = []
        if len(parts) > 1:
            rest = parts[1].strip()
            if rest.startswith("merge "):
                args = ["merge", rest[6:].strip()]
            elif rest.startswith("replace "):
                args = ["replace", rest[8:].strip()]
            else:
                args = [rest]
        tokens = [verb] + args
    else:
        try:
            tokens = shlex.split(trimmed)
        except ValueError as err:
            return f"{C_RED}Syntax Error: {str(err)}{C_RESET}"

    if not tokens:
        return ""

    verb = tokens[0].lower()
    args = tokens[1:]

    if verb in ("clear", "cls", "c"):
        return "__CLEAR_SCREEN__"

    if verb not in COMMANDS:
        return f"{C_RED}Unknown command: '{verb}'. Type 'help' for options.{C_RESET}"

    handler = COMMANDS[verb]
    try:
        if inspect.iscoroutinefunction(handler):
            return await handler(args)
        return handler(args)
    except Exception as e:
        return f"{C_RED}Execution error in '{verb}': {str(e)}{C_RESET}"
