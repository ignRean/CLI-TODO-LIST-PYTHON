"""
PhD Consortium Exhaustive Unit & Integration Test Suite for PyTodo Natural Language Parser
Author: Dr. Marcus Sterling (Lead Cybernetics & Red Teamer)
Target: main.py (Natural Language Task & Subtask Parser Engine)
"""

import sys
import os
import json
import uuid
import re
import unittest
import types
import asyncio
from datetime import datetime, timezone, timedelta

# Ensure parent directory is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------------------------------------------------------
# Mock Environment Setup (Pyodide & JS Bridge Interop)
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
        self.last_payload = None
        self.dashboard_mode = False
        self.terminal_cols = 80
        self.iso_date = "2026-09-20"
        self.sounds_played = []
        self.pairing_code = ""
        self.sync_status = "IDLE"
        self.sync_triggered = False
        self.theme = "classic"
        self.retention_days = 3
        self.sound = True

    def getFocusStep(self):
        return self.step_sec

    def setFocusStep(self, sec):
        self.step_sec = int(sec)

    def enterFocusMode(self, payload_str):
        self.last_payload = json.loads(payload_str)

    def triggerBackgroundSync(self):
        self.sync_triggered = True

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
        return getattr(self, "theme", "classic")

    def setTheme(self, name):
        self.theme = str(name)
        return self.theme

    def getRetentionDays(self):
        return getattr(self, "retention_days", 3)

    def setRetentionDays(self, days):
        self.retention_days = int(days)
        return True

    def isSoundEnabled(self):
        return getattr(self, "sound", True)

    def setSoundEnabled(self, val):
        self.sound = bool(val)


class MockDate:
    def __init__(self):
        # Midday timestamp on 2026-09-20 12:00:00 UTC
        self.set_datetime(2026, 9, 20, 12, 0, 0)
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


class MockWindow:
    def __init__(self):
        self.localStorage = MockStorage()
        self.PyTodoBridge = MockPyTodoBridge()
        self.Date = MockDate()
        self.term = type("Term", (), {"cols": 80})()


mock_win = MockWindow()
js_mock = types.ModuleType("js")
js_mock.window = mock_win
js_mock.supabaseClient = None
sys.modules["js"] = js_mock

# Import main after setting up the js mock module
from main import (
    sanitize_text,
    get_local_now,
    get_local_date_str,
    get_local_todos,
    save_local_todos,
    set_pairing_code,
    parse_natural_task,
    normalize_duration_str,
    handle_command,
    cli_add,
    cli_edit,
    cli_subtask,
    cli_ls,
    cli_focus,
    get_deadline_info
)


class BasePyTodoTest(unittest.TestCase):
    def setUp(self):
        import main
        main.window = mock_win
        main.supabaseClient = None
        sys.modules["js"].window = mock_win
        sys.modules["js"].supabaseClient = None
        mock_win.localStorage.clear()
        mock_win.PyTodoBridge.step_sec = 300
        mock_win.PyTodoBridge.last_payload = None
        mock_win.PyTodoBridge.terminal_cols = 80
        mock_win.PyTodoBridge.iso_date = "2026-09-20"
        mock_win.PyTodoBridge.sounds_played.clear()
        mock_win.PyTodoBridge.pairing_code = ""
        mock_win.PyTodoBridge.sync_status = "IDLE"
        mock_win.PyTodoBridge.sync_triggered = False
        mock_win.Date.set_datetime(2026, 9, 20, 12, 0, 0)
        save_local_todos([])
        set_pairing_code("")

    def run_cmd(self, line: str) -> str:
        """Helper to run async handle_command synchronously."""
        return asyncio.run(handle_command(line))


# ---------------------------------------------------------
# Suite 1: Primary Task Natural Language Extraction
# ---------------------------------------------------------

class TestPrimaryTaskNaturalLanguageExtraction(BasePyTodoTest):
    """
    Validates natural language deadline and duration parsing on 'add' CLI commands.
    """

    def test_add_finish_presentation_by_5pm_for_45m(self):
        res = self.run_cmd("add Finish presentation by 5pm for 45m")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Finish presentation", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Finish presentation")
        self.assertEqual(task["due_time"], "17:00")
        self.assertEqual(task["duration_minutes"], 45)

    def test_add_team_sync_at_2_30pm(self):
        res = self.run_cmd("add Team sync at 2:30pm")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Team sync", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Team sync")
        self.assertEqual(task["due_time"], "14:30")
        self.assertIsNone(task["duration_minutes"])

    def test_add_workout_for_1h(self):
        res = self.run_cmd("add Workout for 1h")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Workout", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Workout")
        self.assertEqual(task["duration_minutes"], 60)
        self.assertIsNone(task["due_time"])

    def test_add_deep_work_for_1h_and_30m_by_18_00(self):
        res = self.run_cmd("add Deep work for 1h and 30m by 18:00")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Deep work", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Deep work")
        self.assertEqual(task["due_time"], "18:00")
        self.assertEqual(task["duration_minutes"], 90)

    def test_add_deploy_hotfix_in_45m(self):
        # Current mocked time is 12:00:00 -> in 45m should resolve to 12:45
        res = self.run_cmd("add Deploy hotfix in 45m")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Deploy hotfix", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Deploy hotfix")
        self.assertEqual(task["due_time"], "12:45")

    def test_add_submit_taxes_by_tomorrow_6pm(self):
        # Current mocked date is 2026-09-20 -> tomorrow is 2026-09-21
        res = self.run_cmd("add Submit taxes by tomorrow 6pm")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Submit taxes", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Submit taxes")
        self.assertEqual(task["task_date"], "2026-09-21")
        self.assertEqual(task["due_time"], "18:00")

    def test_inverted_clause_ordering(self):
        # Clauses positioned before the task name
        res = self.run_cmd("add for 45m by 5pm Finalize Quarterly Ledger")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Finalize Quarterly Ledger", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Finalize Quarterly Ledger")
        self.assertEqual(task["due_time"], "17:00")
        self.assertEqual(task["duration_minutes"], 45)


# ---------------------------------------------------------
# Suite 2: Subtask Natural Language Extraction
# ---------------------------------------------------------

class TestSubtaskNaturalLanguageExtraction(BasePyTodoTest):
    """
    Validates natural language extraction on subtasks across one-shot add,
    dedicated subtask command, and edit --add-sub command, plus rendering in ls.
    """

    def test_one_shot_subtask_in_add(self):
        res = self.run_cmd('add "Release v2" -s "Draft notes at 3pm for 20m" -s "Tag release by 5pm"')
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)
        self.assertIn("Release v2", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["title"], "Release v2")
        self.assertEqual(len(task["subtasks"]), 2)

        sub1 = task["subtasks"][0]
        self.assertEqual(sub1["title"], "Draft notes")
        self.assertEqual(sub1["due_time"], "15:00")
        self.assertEqual(sub1["duration_minutes"], 20)

        sub2 = task["subtasks"][1]
        self.assertEqual(sub2["title"], "Tag release")
        self.assertEqual(sub2["due_time"], "17:00")
        self.assertIsNone(sub2["duration_minutes"])

    def test_dedicated_subtask_command(self):
        # First add parent task
        self.run_cmd("add Feature Sprint")
        # Add subtask via dedicated command
        res = self.run_cmd("subtask 1 Review PR at 4pm for 15m")
        clean = sanitize_text(res)
        self.assertIn("[✔] Task '1' updated:", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(len(task["subtasks"]), 1)
        sub = task["subtasks"][0]
        self.assertEqual(sub["title"], "Review PR")
        self.assertEqual(sub["due_time"], "16:00")
        self.assertEqual(sub["duration_minutes"], 15)

    def test_edit_command_add_sub(self):
        # First add parent task
        self.run_cmd("add Maintenance Sprint")
        # Add subtask via edit --add-sub
        res = self.run_cmd('edit 1 --add-sub "Update docs by 6pm"')
        clean = sanitize_text(res)
        self.assertIn("[✔] Task '1' updated:", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(len(task["subtasks"]), 1)
        sub = task["subtasks"][0]
        self.assertEqual(sub["title"], "Update docs")
        self.assertEqual(sub["due_time"], "18:00")
        self.assertIsNone(sub["duration_minutes"])

    def test_subtask_rendering_in_ls_mode_a_and_mode_b(self):
        # Create task with detailed subtask
        self.run_cmd('add "Project Falcon" -s "Draft notes at 3pm for 20m" -s "Tag release by 5pm"')

        # Test Mode B (Desktop / Table mode, width = 100 cols)
        mock_win.PyTodoBridge.terminal_cols = 100
        ls_b = self.run_cmd("ls")
        clean_b = sanitize_text(ls_b)
        self.assertIn("Project Falcon", clean_b)
        self.assertIn("Draft notes", clean_b)
        self.assertIn("20m", clean_b)
        self.assertTrue("SOON" in clean_b or "15:00" in clean_b)
        self.assertIn("Tag release", clean_b)
        self.assertIn("17:00", clean_b)

        # Test Mode A (Mobile mode, width = 50 cols)
        mock_win.PyTodoBridge.terminal_cols = 50
        ls_a = self.run_cmd("ls")
        clean_a = sanitize_text(ls_a)
        self.assertIn("Project Falcon", clean_a)
        self.assertIn("Draft notes", clean_a)
        self.assertIn("20m", clean_a)
        self.assertTrue("SOON" in clean_a or "15:00" in clean_a)
        self.assertIn("Tag release", clean_a)
        self.assertIn("17:00", clean_a)


# ---------------------------------------------------------
# Suite 3: Flag Precedence (POSIX overrides)
# ---------------------------------------------------------

class TestFlagPrecedencePOSIXOverrides(BasePyTodoTest):
    """
    Validates POSIX override rules: explicit CLI flags strictly override
    natural language heuristics, and the clause in the title is preserved.
    """

    def test_explicit_due_overrides_nl_due(self):
        res = self.run_cmd("add Finish report by 5pm --due 18:00")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        # Explicit flag wins
        self.assertEqual(task["due_time"], "18:00")
        # Literal title preserves text to avoid silent loss
        self.assertEqual(task["title"], "Finish report by 5pm")

    def test_explicit_duration_overrides_nl_duration(self):
        res = self.run_cmd("add Workout for 1h --duration 30m")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        # Explicit flag wins
        self.assertEqual(task["duration_minutes"], 30)
        # Literal title preserves text to avoid silent loss
        self.assertEqual(task["title"], "Workout for 1h")

    def test_explicit_both_flags_override(self):
        res = self.run_cmd("add Deep work by 5pm for 1h --due 19:00 --duration 45m")
        clean = sanitize_text(res)
        self.assertIn("[+] Task added:", clean)

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        task = todos[0]
        self.assertEqual(task["due_time"], "19:00")
        self.assertEqual(task["duration_minutes"], 45)
        self.assertEqual(task["title"], "Deep work by 5pm for 1h")


# ---------------------------------------------------------
# Suite 4: Adversarial False Positive Matrix
# ---------------------------------------------------------

class TestAdversarialFalsePositiveMatrix(BasePyTodoTest):
    """
    Validates that everyday non-temporal English phrases are NOT falsely
    extracted as deadlines or durations.
    """

    def test_beneficiary_phrases_preserve_title_and_no_duration(self):
        # 'for mom'
        self.run_cmd("add Gift for mom")
        # 'for 3 bugs'
        self.run_cmd("add Search for 3 bugs")
        # 'for email'
        self.run_cmd("add Wait for email")

        todos = get_local_todos()
        self.assertEqual(len(todos), 3)

        self.assertEqual(todos[0]["title"], "Gift for mom")
        self.assertIsNone(todos[0]["duration_minutes"])

        self.assertEqual(todos[1]["title"], "Search for 3 bugs")
        self.assertIsNone(todos[1]["duration_minutes"])

        self.assertEqual(todos[2]["title"], "Wait for email")
        self.assertIsNone(todos[2]["duration_minutes"])

    def test_phrasal_and_authorial_by_preserve_title_and_no_due(self):
        # 'by Orwell'
        self.run_cmd("add Read book by Orwell")
        # 'by me'
        self.run_cmd("add Stand by me")

        todos = get_local_todos()
        self.assertEqual(len(todos), 2)

        self.assertEqual(todos[0]["title"], "Read book by Orwell")
        self.assertIsNone(todos[0]["due_time"])

        self.assertEqual(todos[1]["title"], "Stand by me")
        self.assertIsNone(todos[1]["due_time"])

    def test_locational_at_preserves_title_and_no_due(self):
        # 'at cafe'
        self.run_cmd("add Meet at cafe")
        # 'at Chipotle'
        self.run_cmd("add Lunch at Chipotle")

        todos = get_local_todos()
        self.assertEqual(len(todos), 2)

        self.assertEqual(todos[0]["title"], "Meet at cafe")
        self.assertIsNone(todos[0]["due_time"])

        self.assertEqual(todos[1]["title"], "Lunch at Chipotle")
        self.assertIsNone(todos[1]["due_time"])

    def test_financial_and_numeric_counts(self):
        # 'for 2 items'
        self.run_cmd("add Pay $45 for 2 items")

        todos = get_local_todos()
        self.assertEqual(len(todos), 1)

        self.assertEqual(todos[0]["title"], "Pay $45 for 2 items")
        self.assertIsNone(todos[0]["duration_minutes"])
        self.assertIsNone(todos[0]["due_time"])


# ---------------------------------------------------------
# Suite 5: Punctuation & Regression Guards
# ---------------------------------------------------------

class TestPunctuationAndRegressionGuards(BasePyTodoTest):
    """
    Validates edge cases with punctuation, existing test invariants,
    and focus mode duration inheritance.
    """

    def test_trailing_exclamation_mark(self):
        self.run_cmd("add Workout for 45m!")
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Workout!")
        self.assertEqual(todos[0]["duration_minutes"], 45)

    def test_trailing_period(self):
        self.run_cmd("add Call John at 5pm.")
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Call John.")
        self.assertEqual(todos[0]["due_time"], "17:00")

    def test_tomorrow_morning_task_regression_invariant(self):
        # In test_exhaustive_features.py: 'Tomorrow Morning Task' must NOT be parsed as due tomorrow!
        self.run_cmd("add Tomorrow Morning Task")
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Tomorrow Morning Task")
        self.assertEqual(todos[0]["task_date"], "2026-09-20")
        self.assertIsNone(todos[0]["due_time"])

    def test_focus_mode_inherits_subtask_duration(self):
        # Add parent task and subtask with 15m duration
        self.run_cmd('add "Project Falcon" -s "Review PR at 4pm for 15m"')
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["subtasks"][0]["duration_minutes"], 15)

        # Trigger focus mode on subtask 1.1
        self.run_cmd("focus 1.1")
        payload = mock_win.PyTodoBridge.last_payload
        self.assertIsNotNone(payload)
        self.assertEqual(payload["id"], "1.1")
        self.assertEqual(payload["title"], "Review PR")
        # 15m * 60 = 900 seconds
        self.assertEqual(payload["duration_sec"], 900)

    def test_focus_mode_fallback_when_subtask_has_no_duration(self):
        # Add parent task with 45m duration and subtask without duration
        self.run_cmd('add "Project Falcon" --duration 45m -s "Review PR at 4pm"')
        todos = get_local_todos()
        self.assertEqual(len(todos), 1)
        self.assertIsNone(todos[0]["subtasks"][0]["duration_minutes"])

        # Trigger focus mode on subtask 1.1 -> should fallback to parent duration 45m (2700s)
        self.run_cmd("focus 1.1")
        payload = mock_win.PyTodoBridge.last_payload
        self.assertIsNotNone(payload)
        self.assertEqual(payload["id"], "1.1")
        self.assertEqual(payload["duration_sec"], 2700)


# ---------------------------------------------------------
# Suite 6: Direct Engine Micro-Proofs & ReDoS Stress Testing
# ---------------------------------------------------------

class TestDirectEngineMicroProofs(unittest.TestCase):
    """
    Direct micro-proofs and algorithmic complexity / ReDoS stress testing.
    """

    def setUp(self):
        self.now = datetime(2026, 9, 20, 12, 0, 0)

    def test_normalize_duration_str(self):
        self.assertEqual(normalize_duration_str("1h and 30m"), "1h30m")
        self.assertEqual(normalize_duration_str("45 minutes"), "45m")
        self.assertEqual(normalize_duration_str("2 hours"), "2h")
        self.assertEqual(normalize_duration_str("90 secs"), "90s")

    def test_parentheses_removal_cleanup(self):
        res = parse_natural_task("Review draft (by 5pm) for 1h", now=self.now)
        self.assertEqual(res["title"], "Review draft")
        self.assertEqual(res["due_time"], "17:00")
        self.assertEqual(res["duration_minutes"], 60)

    def test_redos_immunity_on_repeated_clauses(self):
        # Red Teaming Stress Test: Construct massive repetitive input
        attack_str = "Task " + ("for 1h and " * 50) + "30m by 18:00"
        start_ts = datetime.now()
        res = parse_natural_task(attack_str, now=self.now)
        elapsed_sec = (datetime.now() - start_ts).total_seconds()

        # Must execute in under 50 milliseconds (guaranteeing O(N) linear time)
        self.assertLess(elapsed_sec, 0.05)
        self.assertEqual(res["due_time"], "18:00")
        self.assertIsNotNone(res["duration_minutes"])


if __name__ == "__main__":
    unittest.main()
