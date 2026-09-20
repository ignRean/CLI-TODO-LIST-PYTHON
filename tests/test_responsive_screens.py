import sys
import os
import json
import re
from unittest.mock import MagicMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Mock browser JS dependencies
mock_window = MagicMock()
mock_storage = {}
def mock_getItem(key): return mock_storage.get(key)
def mock_setItem(key, val): mock_storage[key] = str(val)
def mock_removeItem(key): mock_storage.pop(key, None)

mock_window.localStorage.getItem = mock_getItem
mock_window.localStorage.setItem = mock_setItem
mock_window.localStorage.removeItem = mock_removeItem
mock_window.PyTodoBridge.getLocalISODate.return_value = "2026-09-20"
mock_window.PyTodoBridge.getTerminalCols.return_value = 80
mock_window.PyTodoBridge.triggerBackgroundSync.return_value = None
mock_window.PyTodoBridge.playSound.return_value = None
mock_window.PyTodoBridge.setPairingCode.return_value = None
mock_window.PyTodoBridge.setSyncStatus.return_value = None

sys.modules["js"] = MagicMock()
sys.modules["js"].window = mock_window
sys.modules["js"].supabaseClient = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import main

def populate_test_tasks():
    mock_storage.clear()
    # Task 1: Short task
    main.cli_add(["Review PR", "--due", "14:00"])
    # Task 2: Extra-long task title with multiple subtasks
    main.cli_add([
        "Architect and implement ultra-resilient distributed offline-first terminal synchronization engine",
        "--due", "19:30",
        "-s", "Validate Base32 entropy against birthday collisions across 1 billion space",
        "-s", "Verify zero terminal line wrapping down to 30 columns on mobile",
        "-s", "Check DECAWM auto-wrap lock"
    ])
    # Task 3: Completed task
    main.cli_add(["Write responsive unit tests", "--due", "12:00"])
    main.cli_done(["3"])
    # Task 4: Subtask completion
    main.cli_done(["2.1"])

def test_responsive_cli_ls():
    print("\n========================================================")
    print("[*] TEST SUITE 1: Responsive cli_ls across all viewports")
    print("========================================================")
    
    test_widths = [30, 35, 40, 50, 60, 64, 65, 70, 75, 80, 90, 100, 120, 160]
    
    for width in test_widths:
        mock_window.PyTodoBridge.getTerminalCols.return_value = width
        populate_test_tasks()
        
        output = main.cli_ls([])
        lines = output.splitlines()
        
        print(f"\n--- Checking cli_ls at width = {width} cols ({len(lines)} lines) ---")
        
        for idx, line in enumerate(lines, 1):
            vis_w = main.get_visual_width(line)
            clean = main.sanitize_text(line)
            # Each line's visual width must strictly be <= width
            assert vis_w <= width, (
                f"VIOLATION at {width} cols, line {idx} (vis_width={vis_w} > {width}):\n"
                f"Raw line: {clean}"
            )
        print(f"  ✔ Width {width} passed: all {len(lines)} lines conform to terminal boundary.")

def test_responsive_top_dashboard():
    print("\n========================================================")
    print("[*] TEST SUITE 2: Responsive get_dashboard_frame (top/watch)")
    print("========================================================")
    
    test_widths = [30, 35, 40, 50, 60, 65, 75, 80, 100, 120, 160]
    
    for width in test_widths:
        mock_window.PyTodoBridge.getTerminalCols.return_value = width
        populate_test_tasks()
        
        frame = main.get_dashboard_frame()
        lines = frame.splitlines()
        
        print(f"\n--- Checking top dashboard at width = {width} cols ({len(lines)} lines) ---")
        
        for idx, line in enumerate(lines, 1):
            vis_w = main.get_visual_width(line)
            clean = main.sanitize_text(line)
            assert vis_w <= width, (
                f"VIOLATION in top dashboard at {width} cols, line {idx} (vis_width={vis_w} > {width}):\n"
                f"Raw line: {clean}"
            )
        print(f"  ✔ Width {width} passed: all {len(lines)} lines conform to terminal boundary.")

def test_base32_pairing_architecture():
    print("\n========================================================")
    print("[*] TEST SUITE 3: Base32 Pairing Code & Account Security")
    print("========================================================")
    
    mock_storage.clear()
    
    # 1. Test Base32 Generator
    codes = set()
    b32_alphabet = set("23456789ABCDEFGHJKMNPQRSTUVWXYZ")
    for _ in range(1000):
        c = main.generate_unique_pairing_code()
        assert len(c) == 6, f"Invalid code length: {len(c)}"
        assert set(c).issubset(b32_alphabet), f"Invalid characters in code {c}"
        # Ambiguous characters must NEVER appear
        assert "0" not in c, f"Ambiguous '0' found in {c}"
        assert "O" not in c, f"Ambiguous 'O' found in {c}"
        assert "1" not in c, f"Ambiguous '1' found in {c}"
        assert "I" not in c, f"Ambiguous 'I' found in {c}"
        assert "L" not in c, f"Ambiguous 'L' found in {c}"
        codes.add(c)
    assert len(codes) == 1000, "Collision detected in 1000 samples"
    print("  ✔ 1,000 Base32 codes generated with 0 collisions and 0 ambiguous chars.")

    # 2. Test 'code' command when not linked
    import asyncio
    res_code_unlinked = asyncio.run(main.cli_code([]))
    assert "not linked" in res_code_unlinked.lower(), "Should report unlinked"
    print("  ✔ 'code' command handles unlinked state gracefully.")

    # 3. Test 'link generate' creates key
    res_gen = asyncio.run(main.cli_link(["generate"]))
    assert "Pairing key generated:" in res_gen
    active_code = main.get_pairing_code()
    assert len(active_code) == 6
    assert set(active_code).issubset(b32_alphabet)
    print(f"  ✔ Generated pairing key: {active_code}")

    # 4. Test 'code' command displays active key
    res_code_linked = asyncio.run(main.cli_code([]))
    assert active_code in res_code_linked
    print("  ✔ 'code' command displays active key correctly.")

    # 5. Test 'link generate' warning when already linked
    res_gen_warn = asyncio.run(main.cli_link(["generate"]))
    assert "Warning: This device is already linked" in res_gen_warn
    assert "--force" in res_gen_warn
    print("  ✔ Re-generation warning guard confirmed.")

    # 6. Test 'link generate --force' re-keys and preserves local tasks
    populate_test_tasks()
    prev_count = len(main.get_local_todos())
    assert prev_count > 0
    res_gen_force = asyncio.run(main.cli_link(["generate", "--force"]))
    assert "Pairing key generated:" in res_gen_force
    new_code = main.get_pairing_code()
    assert new_code != active_code
    new_todos = main.get_local_todos()
    assert len(new_todos) == prev_count, "Local tasks must NOT be deleted on re-keying"
    for t in new_todos:
        assert t["pairing_code"] == new_code, "Task pairing_code must be re-keyed"
    print(f"  ✔ Force re-keying to {new_code} preserved all {prev_count} local tasks.")

    # 7. Test 'link <code_string>' support for Base32 and legacy formats
    res_link_b32 = asyncio.run(main.cli_link(["7K9M2P"]))
    assert main.get_pairing_code() == "7K9M2P"
    print("  ✔ 'link 7K9M2P' accepted.")

    res_link_legacy = asyncio.run(main.cli_link(["849201"]))
    assert main.get_pairing_code() == "849201"
    print("  ✔ 'link 849201' legacy 6-digit accepted.")

    # 8. Test invalid key format rejection
    res_invalid = asyncio.run(main.cli_link(["ABC"]))
    assert "Error:" in res_invalid
    print("  ✔ Invalid code 'ABC' rejected properly.")

    # 9. Test 'unlink'
    res_unlink = asyncio.run(main.cli_unlink([]))
    assert "unlinked" in res_unlink.lower()
    assert not main.get_pairing_code()
    print("  ✔ 'unlink' cleared pairing code.")

if __name__ == "__main__":
    test_responsive_cli_ls()
    test_responsive_top_dashboard()
    test_base32_pairing_architecture()
    print("\n========================================================")
    print("🎉 ALL RESPONSIVE AND SECURITY TESTS PASSED PERFECTLY! [✔]")
    print("========================================================")
