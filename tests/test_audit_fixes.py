"""
Automated Verification Suite for PyTodo 15 Audit Fixes
Authors: Dr. Aris Thorne (Chief Research Scientist), Dr. Elena Vance (Software Architect), Dr. Marcus Sterling (Lead Cybernetics)
Target: Comprehensive audit validation across storage, parsing, invariants, sync, and export/import
"""

import sys
import os
import json
import uuid
import unittest
import types
import asyncio
from datetime import datetime, timezone, timedelta

# Setup paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------------------------------------------------------
# Mock Environment Setup
# ---------------------------------------------------------

class MockStorage:
    def __init__(self):
        self.store = {}

    def getItem(self, key):
        return self.store.get(str(key))

    def setItem(self, key, value):
        self.store[str(key)] = str(value)

    def removeItem(self, key):
        self.store.pop(str(key), None)

    def clear(self):
        self.store.clear()


class MockPyTodoBridge:
    def __init__(self):
        self.step_sec = 300
        self.terminal_cols = 80
        self.iso_date = "2026-09-19"
        self.pairing_code = ""
        self.sync_status = "IDLE"
        self.sounds_played = []
        self.downloads = []
        self.theme = "classic"
        self.retention_days = 3

    def getFocusStep(self):
        return self.step_sec

    def setFocusStep(self, sec):
        self.step_sec = int(sec)

    def triggerBackgroundSync(self):
        pass

    def playSound(self, name):
        self.sounds_played.append(name)

    def getTerminalCols(self):
        return self.terminal_cols

    def getLocalISODate(self):
        return self.iso_date

    def setPairingCode(self, code):
        self.pairing_code = str(code)

    def setSyncStatus(self, status):
        self.sync_status = str(status)

    def getTheme(self):
        return self.theme

    def setTheme(self, name):
        self.theme = str(name)
        return self.theme

    def getRetentionDays(self):
        return self.retention_days

    def setRetentionDays(self, days):
        self.retention_days = int(days)
        return True

    def isSoundEnabled(self):
        return getattr(self, "sound", True)

    def setSoundEnabled(self, val):
        self.sound = bool(val)

    def downloadJSON(self, filename, content):
        self.downloads.append((filename, content))


class MockDate:
    def __init__(self):
        self.set_datetime(2026, 9, 19, 12, 0, 0)
        self._offset = 0

    def set_datetime(self, year, month, day, hour=12, minute=0, second=0):
        dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
        self._now_ts = int(dt.timestamp() * 1000)

    def now(self):
        return self._now_ts

    def new(self):
        offset = self._offset
        return type("DateObj", (), {
            "getTimezoneOffset": lambda s: offset
        })()


class MockQueryBuilder:
    def __init__(self, table_name, db):
        self.table_name = table_name
        self.db = db
        self.action = "select"
        self.filters = {}
        self.payload = None

    def select(self, *args):
        self.action = "select"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def upsert(self, payload):
        self.action = "upsert"
        self.payload = payload
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def in_(self, col, vals):
        self.filters[col + "__in"] = list(vals)
        return self

    def gte(self, col, val):
        self.filters[col + "__gte"] = val
        return self

    def maybeSingle(self):
        return self

    async def execute(self):
        res = type("SupabaseResponse", (), {"data": None, "error": None})()
        if self.action == "select":
            table_data = self.db.tables.get(self.table_name, [])
            filtered = []
            for row in table_data:
                match = True
                for k, v in self.filters.items():
                    if k.endswith("__in"):
                        col = k[:-4]
                        if row.get(col) not in v:
                            match = False
                    elif k.endswith("__gte"):
                        col = k[:-5]
                        if str(row.get(col, "")) < str(v):
                            match = False
                    else:
                        if row.get(k) != v:
                            match = False
                if match:
                    filtered.append(row)
            res.data = filtered
        elif self.action == "insert":
            if self.table_name not in self.db.tables:
                self.db.tables[self.table_name] = []
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            self.db.tables[self.table_name].extend(rows)
            res.data = self.payload
        elif self.action == "upsert":
            if self.table_name not in self.db.tables:
                self.db.tables[self.table_name] = []
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            for r in rows:
                found = False
                for i, ex in enumerate(self.db.tables[self.table_name]):
                    if ex.get("id") == r.get("id") and ex.get("pairing_code") == r.get("pairing_code"):
                        self.db.tables[self.table_name][i] = r
                        found = True
                        break
                if not found:
                    self.db.tables[self.table_name].append(r)
            res.data = self.payload
        elif self.action == "delete":
            table_data = self.db.tables.get(self.table_name, [])
            rem = []
            deleted = []
            for row in table_data:
                match = True
                for k, v in self.filters.items():
                    if k.endswith("__in"):
                        col = k[:-4]
                        if row.get(col) not in v:
                            match = False
                    else:
                        if row.get(k) != v:
                            match = False
                if match:
                    deleted.append(row)
                else:
                    rem.append(row)
            self.db.tables[self.table_name] = rem
            self.db.deleted_rows.extend(deleted)
            res.data = deleted
        return res


class MockSupabaseClient:
    def __init__(self):
        self.tables = {"todos": [], "todo_accounts": [{"pairing_code": "849201"}]}
        self.deleted_rows = []

    def from_(self, table_name):
        return MockQueryBuilder(table_name, self)

    def table(self, table_name):
        return self.from_(table_name)


mock_win = type("MockWindow", (), {
    "localStorage": MockStorage(),
    "PyTodoBridge": MockPyTodoBridge(),
    "Date": MockDate(),
    "term": type("Term", (), {"cols": 80})()
})()

mock_sb = MockSupabaseClient()

js_mock = types.ModuleType("js")
js_mock.window = mock_win
js_mock.supabaseClient = mock_sb
sys.modules["js"] = js_mock

import main
from main import (
    parse_due_input,
    parse_due_time,
    parse_duration_seconds,
    parse_duration,
    get_tombstones,
    save_tombstones,
    add_tombstone,
    get_local_todos,
    save_local_todos,
    cli_add,
    cli_edit,
    cli_rm,
    cli_done,
    cli_sync,
    cli_link,
    cli_export,
    cli_import,
    COMMANDS,
    get_autocomplete_suggestions
)


class TestAuditFixes(unittest.TestCase):
    def setUp(self):
        main.window = mock_win
        sys.modules["js"].window = mock_win
        sys.modules["js"].supabaseClient = mock_sb
        mock_win.localStorage.clear()
        mock_win.PyTodoBridge.downloads.clear()
        mock_sb.tables["todos"] = []
        mock_sb.deleted_rows.clear()
        mock_win.Date.set_datetime(2026, 9, 19, 12, 0, 0)

    # 1. Natural Language & Time Parsing
    def test_due_time_midnight_and_noon(self):
        d, t = parse_due_input("midnight")
        self.assertEqual(t, "23:59")

        d, t = parse_due_input("noon")
        self.assertEqual(t, "12:00")

    def test_due_time_relative_offsets(self):
        now_fixed = datetime(2026, 9, 19, 14, 0, 0)
        d, t = parse_due_input("in 2h", now=now_fixed)
        self.assertEqual(t, "16:00")
        self.assertEqual(d, "2026-09-19")

        d, t = parse_due_input("in 30m", now=now_fixed)
        self.assertEqual(t, "14:30")

        d, t = parse_due_input("in 1.5 hours", now=now_fixed)
        self.assertEqual(t, "15:30")

    def test_negative_and_malformed_times_rejected(self):
        # Negative numbers must not match 24h or 12h
        d, t = parse_due_input("-18:00")
        self.assertIsNone(t)

        d, t = parse_due_input("-6pm")
        self.assertIsNone(t)

        # 0:00pm is invalid 12h time
        d, t = parse_due_input("0:00pm")
        self.assertIsNone(t)

    # 2. Duration Parser Overflow & Invalid Protection
    def test_duration_overflow_and_specials(self):
        self.assertIsNone(parse_duration_seconds("inf"))
        self.assertIsNone(parse_duration_seconds("-inf"))
        self.assertIsNone(parse_duration_seconds("nan"))
        self.assertIsNone(parse_duration_seconds("1e308"))
        self.assertIsNone(parse_duration_seconds("-45m"))
        self.assertIsNone(parse_duration_seconds("0m"))

    def test_duration_bounds_clamping(self):
        # 1440m = 24h = 86400s
        self.assertEqual(parse_duration_seconds("1440"), 86400)
        # Exceeding 1440m plain number is rejected
        self.assertIsNone(parse_duration_seconds("1441"))
        # Valid composite
        self.assertEqual(parse_duration_seconds("1h30m"), 5400)

    # 3. Date Preservation in cli_add
    def test_cli_add_preserves_date_and_time(self):
        res = cli_add(["Prepare", "Q3", "Briefing", "--due", "tomorrow 6pm"])
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Prepare Q3 Briefing")
        self.assertEqual(todos[0]["due_time"], "18:00")
        self.assertEqual(todos[0]["task_date"], "2026-09-20")

    def test_cli_add_date_only_due(self):
        res = cli_add(["Plan", "Roadmap", "--due", "tomorrow"])
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["task_date"], "2026-09-20")
        self.assertIsNone(todos[0]["due_time"])

    # 4. Subtask Invariant Maintenance
    def test_subtask_addition_reopens_completed_task(self):
        cli_add(["Feature", "A"])
        cli_done(["1"])
        todos = get_local_todos()
        self.assertTrue(todos[0]["done"])

        # Add subtask to completed task
        cli_edit(["1", "--add-sub", "Write Unit Tests"])
        todos = get_local_todos()
        self.assertFalse(todos[0]["done"], "Parent task should reopen when incomplete subtask is added")
        self.assertEqual(len(todos[0]["subtasks"]), 1)
        self.assertEqual(todos[0]["subtasks"][0]["id"], "1.1")

    def test_subtask_removal_reindexes_and_checks_completion(self):
        cli_add(["Feature", "B", "-s", "Sub 1", "-s", "Sub 2", "-s", "Sub 3"])
        todos = get_local_todos()
        self.assertEqual(len(todos[0]["subtasks"]), 3)

        # Remove subtask 1.2
        cli_rm(["1.2"])
        todos = get_local_todos()
        self.assertEqual(len(todos[0]["subtasks"]), 2)
        # Verify stable monotonic IDs (Plan 1): 1.1, 1.3
        self.assertEqual(todos[0]["subtasks"][0]["id"], "1.1")
        self.assertEqual(todos[0]["subtasks"][1]["id"], "1.3")
        self.assertEqual(todos[0]["subtasks"][1]["title"], "Sub 3")

    # 5. Tombstones & Sync Integrity
    def test_tombstone_recorded_on_rm(self):
        cli_add(["Disposable", "Task"])
        todos = get_local_todos()
        t_uuid = todos[0]["uuid"]
        self.assertTrue(bool(t_uuid))

        cli_rm(["1"])
        tombstones = get_tombstones()
        self.assertIn(t_uuid, tombstones)

    def test_sync_deletes_remote_tombstone_and_prevents_resurrection(self):
        async def run_sync_test():
            main.set_pairing_code("849201")
            cli_add(["Zombie", "Candidate"])
            t = get_local_todos()[0]
            t_uuid = t["uuid"]

            # Push to remote
            await cli_sync([])
            self.assertEqual(len(mock_sb.tables["todos"]), 1)

            # Delete locally -> records tombstone
            cli_rm(["1"])
            self.assertIn(t_uuid, get_tombstones())

            # Sync again -> should delete remote record and NOT resurrect it
            await cli_sync([])
            self.assertEqual(len(mock_sb.tables["todos"]), 0)
            self.assertEqual(len(get_local_todos()), 0)

        asyncio.run(run_sync_test())

    # 6. Granular Subtask LWW Merge
    def test_granular_subtask_lww_merge(self):
        async def run_merge_test():
            main.set_pairing_code("849201")
            cli_add(["Parent", "Project", "-s", "Sub A", "-s", "Sub B"])
            t = get_local_todos()[0]
            t_uuid = t["uuid"]

            # Populate remote with same task but Sub A marked done remotely at newer timestamp
            rem_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            mock_sb.tables["todos"] = [{
                "id": t_uuid,
                "pairing_code": "849201",
                "task_date": "2026-09-19",
                "title": "Parent Project",
                "due_time": None,
                "duration_minutes": None,
                "done": False,
                "subtasks": [
                    {"id": "1.1", "title": "Sub A", "done": True, "updated_at": rem_ts},
                    {"id": "1.2", "title": "Sub B", "done": False, "updated_at": "2026-09-19T11:00:00+00:00"}
                ],
                "created_at": "2026-09-19T10:00:00+00:00",
                "updated_at": "2026-09-19T12:00:00+00:00"
            }]

            # Local edits title at current time
            cli_edit(["1", "--title", "Parent Project Renamed"])
            await cli_sync([])

            todos = get_local_todos()
            self.assertEqual(todos[0]["title"], "Parent Project Renamed")
            # Sub A was marked done remotely at newer rem_ts -> should be merged as done!
            self.assertTrue(todos[0]["subtasks"][0]["done"])

        asyncio.run(run_merge_test())

    # 7. Backup Export & Import
    def test_export_and_import_restore(self):
        cli_add(["Critical", "Task", "--due", "18:00", "-s", "Sub 1"])
        dumped = cli_export(["json"])
        parsed = json.loads(dumped)
        self.assertEqual(parsed["version"], "2.2.5")
        self.assertEqual(len(parsed["todos"]), 1)
        self.assertEqual(parsed["todos"][0]["title"], "Critical Task")

        # Wipe local
        save_local_todos([])
        self.assertEqual(len(get_local_todos()), 0)

        # Restore
        res = cli_import(["replace", dumped])
        self.assertIn("Backup successfully imported", res)
        restored = get_local_todos()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["title"], "Critical Task")
        self.assertEqual(restored[0]["subtasks"][0]["title"], "Sub 1")

    # 8. Command Registry Verification
    def test_commands_registered(self):
        self.assertIn("export", COMMANDS)
        self.assertIn("import", COMMANDS)
        suggestions = json.loads(get_autocomplete_suggestions(""))
        self.assertIn("export", suggestions)
        self.assertIn("import", suggestions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
