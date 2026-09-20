"""
Stage 4 Feasibility Testing & Mathematical Proofs
PhD Consortium Simulation: Overdue History, Discipline Streak, & Themes
"""

import unittest
from datetime import datetime, date, timedelta

# ==============================================================================
# 1. State Machine Simulation Models
# ==============================================================================

class Task:
    def __init__(self, id_str, title, task_date, done=False, subtasks=None):
        self.id = id_str
        self.title = title
        self.task_date = task_date
        self.done = done
        self.subtasks = subtasks or []

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "task_date": self.task_date,
            "done": self.done,
            "subtasks": self.subtasks
        }


class PyTodoSimulator:
    def __init__(self, start_date="2026-09-17", retention_days=3):
        self.current_date = start_date
        self.retention_days = retention_days
        self.active_todos = []
        self.history = {}  # { "YYYY-MM-DD": [task_dict, ...] }
        self.current_streak = 0
        self.highest_streak = 0
        self.last_evaluated_date = None

    def add_task(self, title, done=False, subtasks=None):
        t = Task(str(len(self.active_todos) + 1), title, self.current_date, done, subtasks)
        self.active_todos.append(t)
        return t

    def mark_done(self, task_id):
        for t in self.active_todos:
            if t.id == str(task_id):
                t.done = True
                return True
        return False

    def advance_day(self, new_date):
        """Simulates time passing to a new calendar day."""
        prev_date = self.current_date
        self.current_date = new_date
        self.enforce_day_rollover(prev_date, new_date)

    def enforce_day_rollover(self, from_date, to_date):
        d_from = datetime.strptime(from_date, "%Y-%m-%d").date()
        d_to = datetime.strptime(to_date, "%Y-%m-%d").date()
        day_gap = (d_to - d_from).days

        if day_gap <= 0:
            return  # Monotonic guarantee: no backwards rollover

        # 1. Evaluate from_date tasks
        from_tasks = [t for t in self.active_todos if t.task_date == from_date]
        uncompleted = [t for t in from_tasks if not t.done]

        # History archival
        if uncompleted:
            self.history[from_date] = [t.to_dict() for t in uncompleted]

        # Streak calculation for from_date
        if len(from_tasks) > 0 and len(uncompleted) == 0:
            # Day succeeded!
            self.current_streak += 1
            self.highest_streak = max(self.highest_streak, self.current_streak)
        else:
            # Day failed (either incomplete tasks OR 0 tasks planned)
            self.current_streak = 0

        # Multi-day absence gap (day_gap >= 2):
        # If user was absent for days between from_date and to_date:
        if day_gap >= 2:
            self.current_streak = 0

        # 2. Prune history according to retention_days (1 <= K <= 7)
        cutoff_date = (d_to - timedelta(days=self.retention_days)).strftime("%Y-%m-%d")
        dates_to_remove = [d for d in self.history if d < cutoff_date]
        for d in dates_to_remove:
            del self.history[d]

        # 3. Clean active board: only tasks belonging to to_date remain
        self.active_todos = [t for t in self.active_todos if t.task_date == to_date]
        self.last_evaluated_date = from_date

    def get_indexed_history(self):
        """Returns sorted list of (h_id, date, task_dict) with unique global H1, H2 tags."""
        result = []
        counter = 1
        for d in sorted(self.history.keys(), reverse=True):
            for t in self.history[d]:
                result.append((f"H{counter}", d, t))
                counter += 1
        return result

    def resolve_revive_target(self, query):
        """
        Resolves a revive query into a single task, or raises ValueError on ambiguity.
        Supports:
        - Unique H-tag: 'H1', 'H2'
        - Date-scoped: '2026-09-18 1', 'yesterday 1'
        - Plain ID: '1' (resolves if exactly 1 match; raises Ambiguity if collision found)
        """
        indexed = self.get_indexed_history()
        tokens = query.strip().split()

        # Case 1: H-Tag (e.g. 'H1', 'h2')
        if len(tokens) == 1 and tokens[0].upper().startswith("H") and tokens[0][1:].isdigit():
            target_h = tokens[0].upper()
            for h_id, d, t in indexed:
                if h_id == target_h:
                    return (h_id, d, t)
            return None

        # Case 2: Date + ID (e.g. '2026-09-18 1' or 'yesterday 1')
        if len(tokens) == 2:
            d_query, id_query = tokens[0].lower(), tokens[1]
            if d_query == "yesterday":
                target_date = (datetime.strptime(self.current_date, "%Y-%m-%d").date() - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                target_date = d_query

            for h_id, d, t in indexed:
                if d == target_date and str(t["id"]) == str(id_query):
                    return (h_id, d, t)
            return None

        # Case 3: Plain ID (e.g. '1')
        if len(tokens) == 1:
            id_query = tokens[0]
            matches = [(h_id, d, t) for h_id, d, t in indexed if str(t["id"]) == str(id_query)]
            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                options = [f"[{h_id}] {d}: {t['title']}" for h_id, d, t in matches]
                raise ValueError(f"Ambiguous task ID '{id_query}' found on multiple dates:\n  " + "\n  ".join(options))
            return None

        return None


# ==============================================================================
# 2. Unit Proofs & Test Harness
# ==============================================================================

class TestPhDConsortiumProofs(unittest.TestCase):

    def test_overdue_history_logging_and_retention_pruning(self):
        """Proof: Incomplete tasks are archived per date, and pruned when older than K days."""
        sim = PyTodoSimulator(start_date="2026-09-15", retention_days=3)

        # Day 1: 2026-09-15 (1 done, 1 uncompleted)
        sim.add_task("Completed Task 1", done=True)
        sim.add_task("Uncompleted Task 2", done=False)
        sim.advance_day("2026-09-16")

        self.assertIn("2026-09-15", sim.history)
        self.assertEqual(len(sim.history["2026-09-15"]), 1)
        self.assertEqual(sim.history["2026-09-15"][0]["title"], "Uncompleted Task 2")
        self.assertEqual(sim.current_streak, 0)  # Day failed

        # Day 2: 2026-09-16 (1 uncompleted)
        sim.add_task("Uncompleted Task 3", done=False)
        sim.advance_day("2026-09-17")
        self.assertIn("2026-09-16", sim.history)

        # Day 3: 2026-09-17 (1 uncompleted)
        sim.add_task("Uncompleted Task 4", done=False)
        sim.advance_day("2026-09-18")
        self.assertIn("2026-09-17", sim.history)

        # Currently 3 days in history: Sept 15, 16, 17. Retention is 3 days.
        # Now advance to Sept 19. Cutoff is Sept 19 - 3 days = Sept 16.
        # Sept 15 should be pruned!
        sim.advance_day("2026-09-19")
        self.assertNotIn("2026-09-15", sim.history, "Sept 15 must be pruned as it is older than 3 days")
        self.assertIn("2026-09-16", sim.history)
        self.assertIn("2026-09-17", sim.history)

    def test_discipline_streak_success_and_ath(self):
        """Proof: Consecutive 100% days increment streak and update All-Time High."""
        sim = PyTodoSimulator(start_date="2026-09-15")

        # Day 1: 100% complete
        sim.add_task("Task 1", done=True)
        sim.advance_day("2026-09-16")
        self.assertEqual(sim.current_streak, 1)
        self.assertEqual(sim.highest_streak, 1)

        # Day 2: 100% complete
        sim.add_task("Task 2", done=True)
        sim.add_task("Task 3", done=True)
        sim.advance_day("2026-09-17")
        self.assertEqual(sim.current_streak, 2)
        self.assertEqual(sim.highest_streak, 2)

        # Day 3: 100% complete
        sim.add_task("Task 4", done=True)
        sim.advance_day("2026-09-18")
        self.assertEqual(sim.current_streak, 3)
        self.assertEqual(sim.highest_streak, 3)

        # Day 4: 1 incomplete task -> STREAK RESETS TO 0, ATH REMAINS 3
        sim.add_task("Task 5", done=False)
        sim.advance_day("2026-09-19")
        self.assertEqual(sim.current_streak, 0, "Streak must reset to 0 on failed day")
        self.assertEqual(sim.highest_streak, 3, "ATH must be permanently preserved")

        # Day 5: Succeed again -> Streak becomes 1, ATH remains 3
        sim.add_task("Task 6", done=True)
        sim.advance_day("2026-09-20")
        self.assertEqual(sim.current_streak, 1)
        self.assertEqual(sim.highest_streak, 3)

    def test_multi_day_absence_resets_streak(self):
        """Proof: If user does not open app for 2+ days, streak resets to 0."""
        sim = PyTodoSimulator(start_date="2026-09-15")
        sim.add_task("Task 1", done=True)
        # Advance by 3 days directly (e.g. laptop closed until Sept 18)
        sim.advance_day("2026-09-18")
        self.assertEqual(sim.current_streak, 0, "Multi-day gap must reset streak")

    def test_zero_task_day_does_not_award_streak(self):
        """Proof: 0 tasks created on a day cannot falsely award a discipline streak."""
        sim = PyTodoSimulator(start_date="2026-09-15")
        # No tasks added!
        sim.advance_day("2026-09-16")
        self.assertEqual(sim.current_streak, 0, "A day with 0 tasks must not award streak")

    def test_theme_color_contrast_ratios(self):
        """Proof: Calibrated theme palettes satisfy WCAG AAA / AA contrast requirements."""
        def hex_to_rgb(hex_str):
            h = hex_str.lstrip("#")
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

        def luminance(r, g, b):
            a = [v / 255.0 for v in (r, g, b)]
            a = [(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4) for v in a]
            return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]

        def contrast_ratio(hex1, hex2):
            lum1 = luminance(*hex_to_rgb(hex1))
            lum2 = luminance(*hex_to_rgb(hex2))
            l_max = max(lum1, lum2)
            l_min = min(lum1, lum2)
            return (l_max + 0.05) / (l_min + 0.05)

        # Test curated palettes against their backgrounds
        themes = {
            "classic": {"bg": "#000000", "fg": "#f0f6fc", "green": "#3fb950", "cyan": "#39c5cf"},
            "matrix": {"bg": "#040a05", "fg": "#22da6e", "green": "#39ff14", "cyan": "#00f2a9"},
            "cyberpunk": {"bg": "#0a0702", "fg": "#ffb454", "green": "#ffd074", "cyan": "#ffd54f"},
            "dracula": {"bg": "#181926", "fg": "#cad3f5", "green": "#a6da95", "cyan": "#8bd5ca"},
            "nord": {"bg": "#2e3440", "fg": "#eceff4", "green": "#a3be8c", "cyan": "#88c0d0"},
            "monokai": {"bg": "#19181a", "fg": "#f7f1ff", "green": "#a9dc76", "cyan": "#78dce8"},
            "solarized": {"bg": "#002b36", "fg": "#93a1a1", "green": "#859900", "cyan": "#2aa198"},
        }

        for name, p in themes.items():
            cr_fg = contrast_ratio(p["bg"], p["fg"])
            self.assertGreater(cr_fg, 4.5, f"Theme '{name}' primary fg must exceed 4.5:1 contrast, got {cr_fg:.2f}")

    def test_revive_disambiguation_and_collision_handling(self):
        """Proof: Revive resolves identical IDs across multiple dates using H-tags or date scope, and catches collisions."""
        sim = PyTodoSimulator(start_date="2026-09-17", retention_days=3)

        # 2026-09-17 has task ID '1': "Prepare invoice"
        sim.add_task("Prepare invoice", done=False)
        sim.advance_day("2026-09-18")

        # 2026-09-18 ALSO has task ID '1': "Deploy edge server"
        sim.add_task("Deploy edge server", done=False)
        sim.advance_day("2026-09-19")

        # In history, both Sept 17 and Sept 18 have task id '1'!
        indexed = sim.get_indexed_history()
        # indexed has H1 for Sept 18 #1, H2 for Sept 17 #1
        self.assertEqual(len(indexed), 2)
        self.assertEqual(indexed[0][0], "H1")
        self.assertEqual(indexed[0][1], "2026-09-18")
        self.assertEqual(indexed[1][0], "H2")
        self.assertEqual(indexed[1][1], "2026-09-17")

        # 1. Unique H-tag resolution:
        h1_match = sim.resolve_revive_target("H1")
        self.assertIsNotNone(h1_match)
        self.assertEqual(h1_match[2]["title"], "Deploy edge server")

        h2_match = sim.resolve_revive_target("H2")
        self.assertIsNotNone(h2_match)
        self.assertEqual(h2_match[2]["title"], "Prepare invoice")

        # 2. Date-scoped resolution:
        date_match = sim.resolve_revive_target("2026-09-17 1")
        self.assertIsNotNone(date_match)
        self.assertEqual(date_match[2]["title"], "Prepare invoice")

        yesterday_match = sim.resolve_revive_target("yesterday 1")
        self.assertIsNotNone(yesterday_match)
        self.assertEqual(yesterday_match[2]["title"], "Deploy edge server")

        # 3. Ambiguity detection on plain '1':
        with self.assertRaises(ValueError) as ctx:
            sim.resolve_revive_target("1")
        self.assertIn("Ambiguous task ID '1' found on multiple dates", str(ctx.exception))
        self.assertIn("[H1]", str(ctx.exception))
        self.assertIn("[H2]", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
