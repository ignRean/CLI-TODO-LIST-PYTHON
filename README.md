# PyTodo CLI ⚡

> **High-urgency, ephemeral terminal to-do system designed to eliminate procrastination through loss aversion, daily accountability, and cross-device synchronization.**

---

## 🌟 Overview

Traditional to-do apps act as digital graveyards for forgotten tasks where items roll over indefinitely. **PyTodo CLI** treats each day as a closed, high-stakes sprint:

- ⏳ **Urgency by Design**: Every task belongs to the current calendar day and expires at midnight.
- 🎯 **Subtask Hierarchies & Deadlines**: Add tasks with strict deadlines (`--due 18:30`), target durations (`--duration 45m`), and nested checkpoints.
- 🔥 **Discipline & Loss Aversion**: Incomplete tasks trigger accountability logs and streak tracking.
- 🌐 **Frictionless PWA & Terminal**: Run natively in your terminal with Python, or in the browser via an instant WebAssembly (Pyodide + xterm.js) Progressive Web Application.
- 🔄 **Cross-Device Sync**: Offline-first storage with frictionless numeric pairing codes and automatic synchronization.

---

## 📂 Repository Structure

```text
├── main.py              # Core Python CLI application & state machine
├── index.html           # Terminal web interface (xterm.js + Pyodide)
├── main.js              # Web client logic, audio synthesis & PWA controller
├── style.css            # Responsive CRT terminal styling
├── sw.js                # Offline PWA service worker
├── manifest.json        # Web app manifest for mobile/desktop installation
├── schema.sql           # Database schema for task storage & audit logs
├── FEATURES.md          # Comprehensive product specification & feature roadmap
├── docs/                # Architecture docs, test verification & audit reports
├── tests/               # Exhaustive unit, integration & browser test suites
└── .gitignore           # Git ignore configurations
```

---

## 🚀 Quick Start

### 1. Running the CLI (Python 3.10+)

Run directly with Python:

```bash
# Display help and commands
python main.py --help

# Frictionless Natural Language Add (Auto-extracts deadline & duration)
python main.py add Finish presentation by 5pm for 45m

# Natural Language with Subtask checkpoint
python main.py add "Launch v2" -s "Deploy backend at 3pm for 20m"

# Traditional explicit flags (fully supported)
python main.py add "Deep Work Block" --duration 90m --due 18:00

# List active daily tasks
python main.py ls

# Mark a task complete
python main.py done 1
```

### 2. Running the Web Application (Local Server)

Launch any static web server:

```bash
# Using Python's built-in HTTP server:
python -m http.server 8000
```

Open `http://localhost:8000` in your web browser. The application will initialize the terminal emulator, load Pyodide WebAssembly, and register the offline Service Worker.

---

## 🧪 Running Tests

The repository includes complete test suites covering unit logic, state transitions, subtask hierarchies, and edge cases:

```bash
# Run exhaustive unit and integration test suite
python tests/test_exhaustive_features.py

# Run focus and discipline rule tests
python tests/test_focus_improvements.py
```

---

## 📜 License

MIT License. Feel free to use, modify, and distribute.
