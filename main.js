// ============================================================================
// PyTodo CLI — High-Urgency Ephemeral Terminal Frontend Engine
// Stack: xterm.js v5.5.0 + FitAddon, Pyodide v0.26.2, Web Audio API, Supabase
// ============================================================================

// --- 1. Cloud Client Configuration ---
const SUPABASE_URL = "https://hbmjlfdvrjmmqufbtieb.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_hRyByLQBULkR7wBZ3i9pVA_i6420Yqs";
let supabaseClient = null;
try {
  if (window.supabase && typeof window.supabase.createClient === "function" && SUPABASE_URL && SUPABASE_ANON_KEY) {
    supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  }
} catch (e) {
  console.warn("[PyTodo] Supabase client initialization error:", e);
}
window.supabaseClient = supabaseClient;

// --- 2. Virtual Terminal Display & Multi-Theme Setup ---
const THEMES = {
  classic: {
    name: "Classic Stealth",
    xterm: {
      background: "#000000",
      foreground: "#f0f6fc",
      cursor: "#58a6ff",
      selectionBackground: "#264f78",
      black: "#010409",
      red: "#ff857f",
      green: "#3fb950",
      yellow: "#f2cc60",
      blue: "#58a6ff",
      magenta: "#bc8cff",
      cyan: "#39c5cf",
      white: "#f0f6fc",
      brightBlack: "#6e7681"
    },
    css: {
      "--term-bg": "#000000",
      "--bar-bg": "#0d1117",
      "--bar-border": "#30363d",
      "--key-bg": "#161b22",
      "--key-border": "#30363d",
      "--key-text": "#c9d1d9",
      "--theme-color": "#000000"
    }
  },
  matrix: {
    name: "Matrix Neon",
    xterm: {
      background: "#050d08",
      foreground: "#00ff66",
      cursor: "#00ff66",
      selectionBackground: "#003b14",
      black: "#030a05",
      red: "#ff5555",
      green: "#00ff66",
      yellow: "#a6e22e",
      blue: "#00cc66",
      magenta: "#00ffaa",
      cyan: "#50fa7b",
      white: "#e6ffe6",
      brightBlack: "#1e4a27"
    },
    css: {
      "--term-bg": "#050d08",
      "--bar-bg": "#08160d",
      "--bar-border": "rgba(0, 255, 102, 0.25)",
      "--key-bg": "#0d2215",
      "--key-border": "rgba(0, 255, 102, 0.35)",
      "--key-text": "#00ff66",
      "--theme-color": "#050d08"
    }
  },
  cyberpunk: {
    name: "Cyberpunk Volt",
    xterm: {
      background: "#0f051d",
      foreground: "#ffee00",
      cursor: "#00f0ff",
      selectionBackground: "#3a105f",
      black: "#0a0214",
      red: "#ff0055",
      green: "#00ff9f",
      yellow: "#ffee00",
      blue: "#00f0ff",
      magenta: "#ff007f",
      cyan: "#00e5ff",
      white: "#fefefe",
      brightBlack: "#5c277a"
    },
    css: {
      "--term-bg": "#0f051d",
      "--bar-bg": "#1a0a33",
      "--bar-border": "rgba(255, 0, 127, 0.35)",
      "--key-bg": "#260e4a",
      "--key-border": "rgba(0, 240, 255, 0.4)",
      "--key-text": "#ffee00",
      "--theme-color": "#0f051d"
    }
  },
  dracula: {
    name: "Dracula Night",
    xterm: {
      background: "#282a36",
      foreground: "#f8f8f2",
      cursor: "#ff79c6",
      selectionBackground: "#44475a",
      black: "#21222c",
      red: "#ff5555",
      green: "#50fa7b",
      yellow: "#f1fa8c",
      blue: "#bd93f9",
      magenta: "#ff79c6",
      cyan: "#8be9fd",
      white: "#f8f8f2",
      brightBlack: "#6272a4"
    },
    css: {
      "--term-bg": "#282a36",
      "--bar-bg": "#1e1f29",
      "--bar-border": "#44475a",
      "--key-bg": "#343746",
      "--key-border": "#6272a4",
      "--key-text": "#f8f8f2",
      "--theme-color": "#282a36"
    }
  },
  nord: {
    name: "Nord Arctic",
    xterm: {
      background: "#2e3440",
      foreground: "#eceff4",
      cursor: "#88c0d0",
      selectionBackground: "#434c5e",
      black: "#3b4252",
      red: "#bf616a",
      green: "#a3be8c",
      yellow: "#ebcb8b",
      blue: "#81a1c1",
      magenta: "#b48ead",
      cyan: "#88c0d0",
      white: "#e5e9f0",
      brightBlack: "#4c566a"
    },
    css: {
      "--term-bg": "#2e3440",
      "--bar-bg": "#242933",
      "--bar-border": "#434c5e",
      "--key-bg": "#3b4252",
      "--key-border": "#4c566a",
      "--key-text": "#eceff4",
      "--theme-color": "#2e3440"
    }
  },
  monokai: {
    name: "Monokai Pro",
    xterm: {
      background: "#272822",
      foreground: "#f8f8f2",
      cursor: "#f92672",
      selectionBackground: "#49483e",
      black: "#1e1f1c",
      red: "#f92672",
      green: "#a6e22e",
      yellow: "#e6db74",
      blue: "#66d9ef",
      magenta: "#ae81ff",
      cyan: "#a1efe4",
      white: "#f8f8f2",
      brightBlack: "#75715e"
    },
    css: {
      "--term-bg": "#272822",
      "--bar-bg": "#1e1f1c",
      "--bar-border": "#49483e",
      "--key-bg": "#3e3d32",
      "--key-border": "#75715e",
      "--key-text": "#f8f8f2",
      "--theme-color": "#272822"
    }
  },
  solarized: {
    name: "Solarized Teal",
    xterm: {
      background: "#002b36",
      foreground: "#93a1a1",
      cursor: "#268bd2",
      selectionBackground: "#073642",
      black: "#073642",
      red: "#dc322f",
      green: "#859900",
      yellow: "#b58900",
      blue: "#268bd2",
      magenta: "#d33682",
      cyan: "#2aa198",
      white: "#eee8d5",
      brightBlack: "#586e75"
    },
    css: {
      "--term-bg": "#002b36",
      "--bar-bg": "#073642",
      "--bar-border": "#586e75",
      "--key-bg": "#0a404f",
      "--key-border": "#657b83",
      "--key-text": "#93a1a1",
      "--theme-color": "#002b36"
    }
  }
};

function getActiveThemeName() {
  const saved = window.localStorage.getItem("py_todo_theme");
  return (saved && THEMES[saved]) ? saved : "classic";
}

function applyTheme(name) {
  const themeKey = THEMES[name] ? name : "classic";
  const def = THEMES[themeKey];
  window.localStorage.setItem("py_todo_theme", themeKey);

  // 1. Update xterm options live (no canvas reconstruction)
  if (window.term && window.term.options) {
    window.term.options.theme = def.xterm;
  }

  // 2. Sync CSS custom properties across root, mobile bar & layout
  const root = document.documentElement;
  for (const [prop, val] of Object.entries(def.css)) {
    root.style.setProperty(prop, val);
  }

  // 3. Update PWA meta theme-color for mobile status bars
  const metaTheme = document.querySelector('meta[name="theme-color"]');
  if (metaTheme && def.css["--theme-color"]) {
    metaTheme.setAttribute("content", def.css["--theme-color"]);
  }

  return themeKey;
}

// --- Shell State, Key History & Modes ---
const TerminalMode = {
  SHELL: "SHELL",
  TOP: "TOP",
  FOCUS: "FOCUS"
};

let currentMode = TerminalMode.SHELL;
let pyodide = null;
let inputBuffer = "";
let cursorIndex = 0;
const commandHistory = [];
let historyIndex = -1;
let draftBuffer = "";
let syncStatus = navigator.onLine ? "SYNCED" : "OFFLINE";
let topDashboardInterval = null;
let promptTickerInterval = null;
let activeFocusSession = null;
let focusInterval = null;
let lastKnownDate = new Date().toLocaleDateString("en-CA");
let lastTimerAdjustTime = 0;
let isCommandRunning = false;

// Initial theme activation before terminal opens
const initialThemeKey = getActiveThemeName();
const term = new Terminal({
  cursorBlink: true,
  cursorStyle: "block",
  scrollback: 500,
  theme: THEMES[initialThemeKey].xterm,
  fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", "DejaVu Sans Mono", monospace',
  fontSize: 13.5,
  lineHeight: 1.2
});

const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);

const terminalContainer = document.getElementById("terminal-container");
const terminalElem = document.getElementById("terminal");
if (terminalElem) {
  terminalElem.innerHTML = "";
}
term.open(terminalElem);
window.term = term;
applyTheme(initialThemeKey);
let resizeRaf = null;
function handleViewportResize() {
  if (resizeRaf) cancelAnimationFrame(resizeRaf);
  resizeRaf = requestAnimationFrame(() => {
    if (window.visualViewport && terminalContainer) {
      const vvHeight = window.visualViewport.height;
      const winHeight = window.innerHeight;
      terminalContainer.style.height = `${vvHeight}px`;
      window.scrollTo(0, 0);

      // Detect virtual keyboard deployment (visualViewport shrink > 120px)
      const isKeyboardOpen = (winHeight - vvHeight) > 120;
      document.body.classList.toggle("keyboard-active", isKeyboardOpen);
    }
    if (fitAddon && term && terminalElem && terminalElem.clientWidth > 0) {
      try { fitAddon.fit(); } catch (e) {}
    }
    if (pyodide && currentMode === TerminalMode.SHELL && inputBuffer.length === 0) {
      updatePromptHeader();
    } else if (term) {
      term.scrollToBottom();
    }
  });
}

handleViewportResize();
term.focus();

window.addEventListener("resize", handleViewportResize);
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", handleViewportResize);
  window.visualViewport.addEventListener("scroll", handleViewportResize);
}

window.addEventListener("click", () => term.focus());
window.addEventListener("touchstart", (e) => {
  const bar = document.getElementById("mobile-bar");
  if (!bar || !bar.contains(e.target)) {
    term.focus();
  }
}, { passive: true });

// --- 3. Web Audio API — Zero-Asset 8-Bit Retro Audio Engine ---
let audioCtx = null;
let activeAudioVoice = null;

function getAudioContext() {
  if (!audioCtx) {
    const AudioClass = window.AudioContext || window.webkitAudioContext;
    if (AudioClass) {
      audioCtx = new AudioClass();
    }
  }
  return audioCtx;
}

// Transparently unlock audio on user's first physical interaction
function unlockAudioGesture() {
  const ctx = getAudioContext();
  if (ctx && ctx.state === "suspended") {
    ctx.resume().catch(() => {});
  }
}
["keydown", "click", "touchstart"].forEach((evt) => {
  window.addEventListener(evt, unlockAudioGesture, { passive: true, once: true });
});

function isSoundGloballyEnabled() {
  try {
    return window.localStorage.getItem("py_sound_enabled") !== "false";
  } catch (e) {
    return true;
  }
}

function playTone(soundType) {
  if (!isSoundGloballyEnabled()) return;
  const validSounds = [
    "done", "subtask", "fail", "wipe",
    "add", "rm", "undone", "alarm", "celebration", "streak",
    "revive", "click", "step_up", "step_down", "theme"
  ];
  if (!validSounds.includes(soundType)) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const executeSound = () => {
      const now = ctx.currentTime;

      // Monophonic voice stealing: fade out prior voice over 8ms to prevent polyphonic DAC clipping
      if (activeAudioVoice) {
        try {
          activeAudioVoice.gain.gain.cancelScheduledValues(now);
          activeAudioVoice.gain.gain.linearRampToValueAtTime(0.0001, now + 0.008);
          activeAudioVoice.osc.stop(now + 0.009);
        } catch (err) {}
      }

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      activeAudioVoice = { osc, gain };

      if (soundType === "done") {
        // Upbeat retro arcade arpeggio: E5 (659Hz) -> G#5 (831Hz) -> B5 (988Hz) -> E6 (1319Hz)
        osc.type = "square";
        osc.frequency.setValueAtTime(659.25, now);
        osc.frequency.setValueAtTime(830.61, now + 0.06);
        osc.frequency.setValueAtTime(987.77, now + 0.12);
        osc.frequency.setValueAtTime(1318.51, now + 0.18);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.32);
        osc.start(now);
        osc.stop(now + 0.32);
      } else if (soundType === "subtask") {
        // High dual-tone chirp: A5 (880Hz) -> E6 (1319Hz)
        osc.type = "triangle";
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.setValueAtTime(1318.51, now + 0.05);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.18);
        osc.start(now);
        osc.stop(now + 0.18);
      } else if (soundType === "fail") {
        // Low descending buzz: 180Hz -> 90Hz
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(180, now);
        osc.frequency.exponentialRampToValueAtTime(90, now + 0.22);
        gain.gain.setValueAtTime(0.1, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);
        osc.start(now);
        osc.stop(now + 0.22);
      } else if (soundType === "wipe") {
        // Descending 8-bit game-over arpeggio: C4 (261Hz) -> G3 (196Hz) -> E3 (164Hz) -> C3 (130Hz)
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(261.63, now);
        osc.frequency.setValueAtTime(196.00, now + 0.1);
        osc.frequency.setValueAtTime(164.81, now + 0.2);
        osc.frequency.setValueAtTime(130.81, now + 0.3);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.55);
        osc.start(now);
        osc.stop(now + 0.55);
      } else if (soundType === "add") {
        // Crisp Ascending Pop: 440Hz -> 880Hz -> 1175Hz
        osc.type = "triangle";
        osc.frequency.setValueAtTime(440.00, now);
        osc.frequency.exponentialRampToValueAtTime(880.00, now + 0.04);
        osc.frequency.setValueAtTime(1174.66, now + 0.05);
        gain.gain.setValueAtTime(0.09, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.085);
        osc.start(now);
        osc.stop(now + 0.085);
      } else if (soundType === "rm") {
        // Crunchy Downward Whoosh / Drop: 240Hz -> 60Hz
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(240.00, now);
        osc.frequency.exponentialRampToValueAtTime(60.00, now + 0.12);
        gain.gain.setValueAtTime(0.09, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
        osc.start(now);
        osc.stop(now + 0.12);
      } else if (soundType === "undone") {
        // Springy Rubber-Band "Boing": 880Hz -> 330Hz -> 587Hz -> 440Hz
        osc.type = "sine";
        osc.frequency.setValueAtTime(880.00, now);
        osc.frequency.exponentialRampToValueAtTime(330.00, now + 0.06);
        osc.frequency.exponentialRampToValueAtTime(587.33, now + 0.11);
        osc.frequency.exponentialRampToValueAtTime(440.00, now + 0.16);
        gain.gain.setValueAtTime(0.09, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.16);
        osc.start(now);
        osc.stop(now + 0.16);
      } else if (soundType === "alarm") {
        // 3-Pulse Resonant Pomodoro Gong: C4 -> E4 -> C5
        osc.type = "triangle";
        osc.frequency.setValueAtTime(261.63, now);
        osc.frequency.setValueAtTime(329.63, now + 0.32);
        osc.frequency.setValueAtTime(523.25, now + 0.64);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.005, now + 0.30);
        gain.gain.setValueAtTime(0.13, now + 0.32);
        gain.gain.exponentialRampToValueAtTime(0.005, now + 0.62);
        gain.gain.setValueAtTime(0.15, now + 0.64);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.40);
        osc.start(now);
        osc.stop(now + 1.40);
      } else if (soundType === "celebration") {
        // 100% Board Clear Victory Fanfare: C5 -> E5 -> G5 -> B5 -> C6 -> E6
        osc.type = "square";
        osc.frequency.setValueAtTime(523.25, now);
        osc.frequency.setValueAtTime(659.25, now + 0.08);
        osc.frequency.setValueAtTime(783.99, now + 0.16);
        osc.frequency.setValueAtTime(987.77, now + 0.24);
        osc.frequency.setValueAtTime(1046.50, now + 0.32);
        osc.frequency.setValueAtTime(1318.51, now + 0.44);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.setValueAtTime(0.11, now + 0.32);
        gain.gain.setValueAtTime(0.12, now + 0.44);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.82);
        osc.start(now);
        osc.stop(now + 0.82);
      } else if (soundType === "streak") {
        // Ascending Brass Square Wave Fanfare with Triumph Vibrato: F4 -> A4 -> C5 -> F5 -> A5 (flutter)
        osc.type = "square";
        osc.frequency.setValueAtTime(349.23, now);
        osc.frequency.setValueAtTime(440.00, now + 0.09);
        osc.frequency.setValueAtTime(523.25, now + 0.18);
        osc.frequency.setValueAtTime(698.46, now + 0.27);
        osc.frequency.setValueAtTime(880.00, now + 0.41);
        osc.frequency.setValueAtTime(888.00, now + 0.46);
        osc.frequency.setValueAtTime(880.00, now + 0.51);
        osc.frequency.setValueAtTime(888.00, now + 0.56);
        osc.frequency.setValueAtTime(880.00, now + 0.61);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.setValueAtTime(0.11, now + 0.27);
        gain.gain.setValueAtTime(0.12, now + 0.41);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.72);
        osc.start(now);
        osc.stop(now + 0.72);
      } else if (soundType === "revive") {
        // Phoenix Resurrection 1-Up: C4 -> E4 -> G4 -> C6
        osc.type = "triangle";
        osc.frequency.setValueAtTime(261.63, now);
        osc.frequency.setValueAtTime(329.63, now + 0.07);
        osc.frequency.setValueAtTime(392.00, now + 0.14);
        osc.frequency.setValueAtTime(1046.50, now + 0.21);
        gain.gain.setValueAtTime(0.09, now);
        gain.gain.linearRampToValueAtTime(0.11, now + 0.21);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.42);
        osc.start(now);
        osc.stop(now + 0.42);
      } else if (soundType === "click") {
        // Stopwatch Pause/Resume Click: 1200Hz
        osc.type = "triangle";
        osc.frequency.setValueAtTime(1200.00, now);
        gain.gain.setValueAtTime(0.07, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.02);
        osc.start(now);
        osc.stop(now + 0.02);
      } else if (soundType === "step_up") {
        // High micro click for +: 1500Hz
        osc.type = "sine";
        osc.frequency.setValueAtTime(1500.00, now);
        gain.gain.setValueAtTime(0.06, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.028);
        osc.start(now);
        osc.stop(now + 0.028);
      } else if (soundType === "step_down") {
        // Low micro click for -: 800Hz
        osc.type = "sine";
        osc.frequency.setValueAtTime(800.00, now);
        gain.gain.setValueAtTime(0.06, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.028);
        osc.start(now);
        osc.stop(now + 0.028);
      } else if (soundType === "theme") {
        // Sci-Fi Analog Filter Sweep: 300Hz -> 1200Hz -> 600Hz
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(300.00, now);
        osc.frequency.exponentialRampToValueAtTime(1200.00, now + 0.14);
        osc.frequency.exponentialRampToValueAtTime(600.00, now + 0.22);
        gain.gain.setValueAtTime(0.07, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);
        osc.start(now);
        osc.stop(now + 0.22);
      }

      osc.onended = () => {
        try {
          osc.disconnect();
          gain.disconnect();
          if (activeAudioVoice && activeAudioVoice.osc === osc) {
            activeAudioVoice = null;
          }
        } catch (err) {}
      };
    };

    if (ctx.state === "suspended") {
      ctx.resume().then(executeSound).catch(() => {});
    } else {
      executeSound();
    }
  } catch (e) {
    // Non-fatal: Audio failures should never block CLI commands
  }
}

// --- 4. PyTodo JavaScript <-> Python Bridge API ---
window.PyTodoBridge = {
  playSound: (soundType) => playTone(soundType),
  setSoundEnabled: (enabled) => {
    window.localStorage.setItem("py_sound_enabled", enabled ? "true" : "false");
  },
  isSoundEnabled: () => window.localStorage.getItem("py_sound_enabled") !== "false",

  setPairingCode: (code) => {
    if (code) {
      window.localStorage.setItem("py_todo_pairing_code", code);
    } else {
      window.localStorage.removeItem("py_todo_pairing_code");
    }
    updatePromptHeader();
  },
  getPairingCode: () => window.localStorage.getItem("py_todo_pairing_code") || "",

  setSyncStatus: (status) => {
    syncStatus = status;
    updatePromptHeader();
  },
  getSyncStatus: () => syncStatus,

  getLocalISODate: () => new Date().toLocaleDateString("en-CA"),

  triggerBackgroundSync: () => {
    debounceSync();
  },

  enterDashboardMode: (isFull = false) => {
    enterTopDashboard(isFull);
  },
  exitDashboardMode: () => {
    exitTopDashboard();
  },
  isDashboardActive: () => currentMode === TerminalMode.TOP,

  enterFocusMode: (payload) => {
    enterFocusMode(payload);
  },
  exitFocusMode: () => {
    exitFocusMode();
  },
  isFocusActive: () => currentMode === TerminalMode.FOCUS,
  getTerminalCols: () => (term && term.cols ? term.cols : 80),
  getFocusStep: () => {
    try {
      const raw = window.localStorage.getItem("py_focus_step_sec");
      if (raw !== null) {
        const val = parseInt(raw, 10);
        if (!isNaN(val) && val >= 10 && val <= 7200) {
          return val;
        }
      }
    } catch (e) {}
    return 300;
  },
  setFocusStep: (sec) => {
    const s = parseInt(sec, 10);
    if (isNaN(s) || s < 10 || s > 7200) {
      throw new Error(`Step duration must be between 10s and 120m (received ${sec})`);
    }
    window.localStorage.setItem("py_focus_step_sec", String(s));
    return true;
  },

  downloadJSON: (filename, content) => {
    try {
      const blob = new Blob([content], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("[Bridge] downloadJSON error:", e);
    }
  },

  // Multi-Theme Controls
  setTheme: (name) => applyTheme(name),
  getTheme: () => getActiveThemeName(),
  getAvailableThemes: () => JSON.stringify(Object.keys(THEMES)),

  // Retention Window Configuration (1 - 7 days, default 3)
  getRetentionDays: () => {
    try {
      const val = parseInt(window.localStorage.getItem("py_todo_retention_days"), 10);
      if (!isNaN(val) && val >= 1 && val <= 7) return val;
    } catch (e) {}
    return 3;
  },
  setRetentionDays: (days) => {
    const d = parseInt(days, 10);
    if (isNaN(d) || d < 1 || d > 7) {
      throw new Error(`Retention days must be between 1 and 7 (received ${days})`);
    }
    window.localStorage.setItem("py_todo_retention_days", String(d));
    return true;
  },

  // Discipline Streak & History Storage Interop
  getStreakData: () => window.localStorage.getItem("py_todo_streak") || "",
  setStreakData: (jsonStr) => {
    if (jsonStr) {
      window.localStorage.setItem("py_todo_streak", jsonStr);
    } else {
      window.localStorage.removeItem("py_todo_streak");
    }
  },
  getHistoryData: () => window.localStorage.getItem("py_todo_history") || "{}",
  setHistoryData: (jsonStr) => {
    if (jsonStr) {
      window.localStorage.setItem("py_todo_history", jsonStr);
    } else {
      window.localStorage.removeItem("py_todo_history");
    }
  },

  // --- Supabase Cloud Sync Methods (invoked natively from JS to avoid Pyodide PostgREST Thenable proxying) ---
  supabaseInsertAccount: async (candidate) => {
    if (!window.supabaseClient) return JSON.stringify({ error: "Supabase client not initialized" });
    try {
      const { error } = await window.supabaseClient
        .from("todo_accounts")
        .insert({ pairing_code: candidate });
      return JSON.stringify({ error: error ? error.message : null });
    } catch (err) {
      return JSON.stringify({ error: err.message || String(err) });
    }
  },

  supabaseCheckAccount: async (code) => {
    if (!window.supabaseClient) return JSON.stringify({ error: "Supabase client not initialized" });
    try {
      const { data, error } = await window.supabaseClient
        .from("todo_accounts")
        .select("pairing_code")
        .eq("pairing_code", code);
      return JSON.stringify({ data: data || [], error: error ? error.message : null });
    } catch (err) {
      return JSON.stringify({ data: [], error: err.message || String(err) });
    }
  },

  supabaseDeleteTombstones: async (pairingCode, tombstonesJson) => {
    if (!window.supabaseClient) return JSON.stringify({ error: "Supabase client not initialized" });
    try {
      const tombstones = typeof tombstonesJson === "string" ? JSON.parse(tombstonesJson) : tombstonesJson;
      const { error } = await window.supabaseClient
        .from("todos")
        .delete()
        .eq("pairing_code", pairingCode)
        .in("id", tombstones);
      return JSON.stringify({ error: error ? error.message : null });
    } catch (err) {
      return JSON.stringify({ error: err.message || String(err) });
    }
  },

  supabaseFetchTodos: async (pairingCode, todayDate) => {
    if (!window.supabaseClient) return JSON.stringify({ error: "Supabase client not initialized" });
    try {
      const { data, error } = await window.supabaseClient
        .from("todos")
        .select("*")
        .eq("pairing_code", pairingCode)
        .gte("task_date", todayDate);
      return JSON.stringify({ data: data || [], error: error ? error.message : null });
    } catch (err) {
      return JSON.stringify({ data: [], error: err.message || String(err) });
    }
  },

  supabaseUpsertTodos: async (batchPayloadJson) => {
    if (!window.supabaseClient) return JSON.stringify({ error: "Supabase client not initialized" });
    try {
      const payload = typeof batchPayloadJson === "string" ? JSON.parse(batchPayloadJson) : batchPayloadJson;
      const { error } = await window.supabaseClient
        .from("todos")
        .upsert(payload);
      return JSON.stringify({ error: error ? error.message : null });
    } catch (err) {
      return JSON.stringify({ error: err.message || String(err) });
    }
  }
};

// --- 6. Live Telemetry Prompt & Header Banner ---
function formatCountdown(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
}

function getSyncBadge() {
  if (!navigator.onLine || syncStatus === "OFFLINE") {
    return "\x1b[90m[○ OFFLINE]\x1b[0m";
  }
  if (syncStatus === "SYNCING") {
    return "\x1b[33m[◐ SYNCING]\x1b[0m";
  }
  return "\x1b[32m[● SYNCED]\x1b[0m";
}

function stripAnsi(str) {
  return (str || "").replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
}

function getDisplayWidth(str) {
  const clean = stripAnsi(str);
  let w = 0;
  for (const ch of clean) {
    const code = ch.codePointAt(0);
    if (
      (code >= 0x1f300 && code <= 0x1f9ff) ||
      (code >= 0x2600 && code <= 0x27bf) ||
      (code >= 0x2e80 && code <= 0x9fff) ||
      (code >= 0xff01 && code <= 0xff60)
    ) {
      w += 2;
    } else {
      w += 1;
    }
  }
  return w;
}

function truncateAnsi(str, maxCols) {
  if (maxCols <= 0) return "";
  let cur = 0;
  let out = "";
  let esc = "";
  let inEsc = false;

  for (let i = 0; i < str.length; i++) {
    const c = str[i];
    if (c === "\x1b") {
      inEsc = true;
      esc = c;
      continue;
    }
    if (inEsc) {
      esc += c;
      if (/[a-zA-Z]/.test(c)) {
        inEsc = false;
        out += esc;
      }
      continue;
    }
    const code = c.codePointAt(0);
    const cw = ((code >= 0x1f300 && code <= 0x1f9ff) || (code >= 0x2600 && code <= 0x27bf)) ? 2 : 1;
    if (cur + cw > maxCols) break;
    out += c;
    cur += cw;
  }
  return out + "\x1b[0m";
}

function getPromptBanner() {
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const diffSec = Math.max(0, Math.floor((midnight - now) / 1000));
  const countdownStr = formatCountdown(diffSec);
  const miniCountdown = `${Math.floor(diffSec / 3600)}h${Math.floor((diffSec % 3600) / 60)}m`;
  const dateStr = now.toLocaleDateString("en-CA");
  const cols = term && term.cols ? term.cols : 80;
  const maxSafeWidth = Math.max(16, cols - 1);

  let taskProgress = "";
  let doneCount = 0;
  let totalCount = 0;
  try {
    const raw = window.localStorage.getItem("py_pwa_todos");
    if (raw) {
      const todos = JSON.parse(raw);
      if (Array.isArray(todos) && todos.length > 0) {
        totalCount = todos.length;
        doneCount = todos.filter((t) => t.done).length;
        taskProgress = ` | ${doneCount}/${totalCount} Done`;
      }
    }
  } catch (e) {}

  // Discipline streak flame indicator
  let streakBadge = "";
  let streakNum = 0;
  try {
    const rawStreak = window.localStorage.getItem("py_todo_streak");
    if (rawStreak) {
      const streakObj = JSON.parse(rawStreak);
      streakNum = parseInt(streakObj.current_streak, 10) || 0;
      if (streakNum > 0) {
        streakBadge = ` | \x1b[1;33m🔥${streakNum}\x1b[90m`;
      }
    }
  } catch (e) {}

  const pairing = window.localStorage.getItem("py_todo_pairing_code") || "";
  const linkBadge = pairing ? ` | \x1b[36m#${pairing}\x1b[90m` : "";
  const syncBadge = getSyncBadge();

  let banner = "";
  if (cols >= 78) {
    banner = `\x1b[90m[${dateStr}${streakBadge} | ${countdownStr} to Midnight${taskProgress}${linkBadge} | ${syncBadge}\x1b[90m]\x1b[0m`;
  } else if (cols >= 55) {
    const taskPart = totalCount > 0 ? ` | ${doneCount}/${totalCount}` : "";
    banner = `\x1b[90m[${countdownStr}${streakBadge}${taskPart} | ${syncBadge}\x1b[90m]\x1b[0m`;
  } else if (cols >= 36) {
    const sPart = streakNum > 0 ? ` \x1b[1;33m🔥${streakNum}\x1b[90m` : "";
    const taskPart = totalCount > 0 ? ` ${doneCount}/${totalCount}` : "";
    const sBadge = navigator.onLine ? "\x1b[32m[●]\x1b[90m" : "\x1b[90m[○]\x1b[90m";
    banner = `\x1b[90m[${miniCountdown}${sPart}${taskPart} | ${sBadge}]\x1b[0m`;
  } else {
    const sPart = streakNum > 0 ? ` \x1b[1;33m🔥${streakNum}\x1b[90m` : "";
    const sDot = navigator.onLine ? "\x1b[32m●\x1b[90m" : "\x1b[90m○\x1b[90m";
    banner = `\x1b[90m[${miniCountdown}${sPart} ${sDot}]\x1b[0m`;
  }

  if (getDisplayWidth(banner) > maxSafeWidth) {
    banner = truncateAnsi(banner, maxSafeWidth);
  }
  return banner;
}

function renderPrompt(newline = true) {
  if (currentMode !== TerminalMode.SHELL) return;
  const banner = getPromptBanner();
  if (newline) {
    term.write(`\x1b[0m\r\n\x1b[?7l${banner}\x1b[?7h\r\n\x1b[1;36mtodo>\x1b[0m `);
  } else {
    updatePromptHeader();
  }
}

function updatePromptHeader() {
  // Update in place only if user has not typed anything
  if (currentMode === TerminalMode.SHELL && inputBuffer.length === 0) {
    const banner = getPromptBanner();
    term.write(`\x1b[?7l\r\x1b[K\x1b[1A\r\x1b[K${banner}\x1b[1E\r\x1b[K\x1b[1;36mtodo>\x1b[0m \x1b[?7h`);
  }
}

// Background idle ticker for the countdown banner
promptTickerInterval = setInterval(() => {
  if (currentMode === TerminalMode.SHELL && inputBuffer.length === 0) {
    updatePromptHeader();
  }
}, 1000);

// --- 7. Midnight Rollover & Day Transition Engine ---
async function triggerDayTransitionCheck() {
  const currentDate = new Date().toLocaleDateString("en-CA");
  if (currentDate !== lastKnownDate) {
    lastKnownDate = currentDate;
    if (pyodide) {
      try {
        const wiped = await pyodide.runPythonAsync("check_midnight_wipe()");
        if (Number(wiped) > 0) {
          term.writeln(`\r\n\x1b[1;31m[!] MIDNIGHT WIPED: ${wiped} uncompleted tasks moved to history for the new day.\x1b[0m`);
          playTone("wipe");
          renderPrompt();
        } else {
          updatePromptHeader();
        }
      } catch (err) {
        console.error("Day transition check error:", err);
      }
    }
  }
}

// Check every 10 seconds while active
setInterval(triggerDayTransitionCheck, 10000);

// Page Visibility Lifecycle: Pause tickers when tab is hidden, wake up & check date immediately on return
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    if (promptTickerInterval) {
      clearInterval(promptTickerInterval);
      promptTickerInterval = null;
    }
  } else {
    // Waking up from sleep / background: execute day transition check immediately
    triggerDayTransitionCheck();
    if (!promptTickerInterval && currentMode === TerminalMode.SHELL) {
      updatePromptHeader();
      promptTickerInterval = setInterval(() => {
        if (currentMode === TerminalMode.SHELL && inputBuffer.length === 0) {
          updatePromptHeader();
        }
      }, 1000);
    }
  }
});

window.addEventListener("focus", () => {
  triggerDayTransitionCheck();
});

// --- 8. Offline-First Auto-Sync Background Daemon ---
let syncDebounceTimer = null;

function debounceSync() {
  if (syncDebounceTimer) clearTimeout(syncDebounceTimer);
  syncDebounceTimer = setTimeout(async () => {
    if (!pyodide || !navigator.onLine) return;
    const pairing = window.localStorage.getItem("py_todo_pairing_code");
    if (!pairing) return;

    try {
      syncStatus = "SYNCING";
      updatePromptHeader();
      const res = await pyodide.runPythonAsync("cli_sync([])");
      if (res && (String(res).toLowerCase().includes("error") || String(res).includes("[!]"))) {
        syncStatus = "OFFLINE";
      } else {
        syncStatus = "SYNCED";
      }
      updatePromptHeader();
    } catch (e) {
      syncStatus = "OFFLINE";
      updatePromptHeader();
    }
  }, 500);
}

// Reconnect listener
window.addEventListener("online", () => {
  syncStatus = "SYNCING";
  updatePromptHeader();
  debounceSync();
});

window.addEventListener("offline", () => {
  syncStatus = "OFFLINE";
  updatePromptHeader();
});

// Periodic heartbeat sync every 35s
setInterval(() => {
  if (navigator.onLine && window.localStorage.getItem("py_todo_pairing_code")) {
    debounceSync();
  }
}, 35000);

// --- 9. Live HTOP Dashboard Engine (`top` / `watch`) ---
function enterTopDashboard(isFullscreen = false) {
  if (currentMode === TerminalMode.TOP) return;
  if (isFullscreen && document.documentElement.requestFullscreen) {
    document.documentElement.requestFullscreen().catch(() => {});
  }
  currentMode = TerminalMode.TOP;
  term.write("\x1b[?25l\x1b[2J\x1b[H"); // Hide cursor, clear screen, home
  updateMobileBarForMode(TerminalMode.TOP);

  const renderFrame = async () => {
    if (currentMode !== TerminalMode.TOP || !pyodide) return;
    try {
      const frame = await pyodide.runPythonAsync("get_dashboard_frame()");
      if (currentMode === TerminalMode.TOP) {
        term.write(`\x1b[H${frame}\x1b[J`);
      }
    } catch (err) {
      console.error("Dashboard render error:", err);
    }
  };

  renderFrame();
  topDashboardInterval = setInterval(renderFrame, 1000);
}

function exitTopDashboard() {
  if (currentMode !== TerminalMode.TOP) return;
  if (topDashboardInterval) {
    clearInterval(topDashboardInterval);
    topDashboardInterval = null;
  }
  if (document.fullscreenElement && document.exitFullscreen) {
    document.exitFullscreen().catch(() => {});
  }
  currentMode = TerminalMode.SHELL;
  term.write("\x1b[?25h\x1b[2J\x1b[H"); // Restore cursor, clear screen
  updateMobileBarForMode(TerminalMode.SHELL);
  renderPrompt();
}

// --- 9.5. Interactive Pomodoro Focus Mode Engine ---
function fmtTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
}

function fmtStep(sec) {
  if (sec >= 60 && sec % 60 === 0) {
    return `${sec / 60}m`;
  }
  if (sec < 60) {
    return `${sec}s`;
  }
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

function renderFocusSessionFrame() {
  if (currentMode !== TerminalMode.FOCUS || !activeFocusSession) return;
  const s = activeFocusSession;
  const cols = (term && term.cols) ? Math.max(30, term.cols) : 80;
  
  const safeTotal = Math.max(1, s.totalSec);
  const rawPct = (s.elapsedSec / safeTotal) * 100.0;
  const pct = isNaN(rawPct) ? 0.0 : Math.min(100.0, Math.max(0.0, rawPct));
  const remPct = Math.min(100.0, Math.max(0.0, (s.remainingSec / safeTotal) * 100.0));

  const barWidth = Math.max(6, Math.min(36, cols - 24));
  const filled = isNaN(pct) ? 0 : Math.min(barWidth, Math.max(0, Math.floor((pct / 100.0) * barWidth)));

  // Visual Task Ageing color coding
  let barColor = "\x1b[32m";
  if (remPct <= 5.0 || s.remainingSec <= 60) {
    barColor = "\x1b[1;5;31m";
  } else if (remPct <= 15.0 || s.remainingSec <= 180) {
    barColor = "\x1b[38;5;208m";
  } else if (remPct <= 30.0 || s.remainingSec <= 300) {
    barColor = "\x1b[1;33m";
  }

  const bar = barColor + ("=".repeat(filled)) + (filled < barWidth ? ">" : "") + (".".repeat(Math.max(0, barWidth - filled - 1))) + "\x1b[0m";
  
  let stateBadge = "\x1b[1;32m[● ACTIVE]\x1b[0m";
  if (s.remainingSec === 0) {
    stateBadge = "\x1b[1;34m[✔ ELAPSED]\x1b[0m";
  } else if (s.isPaused) {
    stateBadge = "\x1b[1;33m[⏸ PAUSED]\x1b[0m";
  }

  // Responsive Header Banner
  const titleText = " PYTODO FOCUS ENGINE ";
  let headerBanner = "";
  if (cols >= 40) {
    const remaining = Math.max(0, cols - titleText.length);
    const left = Math.floor(remaining / 2);
    const right = remaining - left;
    headerBanner = "\x1b[1;37m" + "=".repeat(left) + titleText + "=".repeat(right) + "\x1b[0m";
  } else {
    headerBanner = "\x1b[1;37m=== FOCUS ENGINE ===\x1b[0m";
  }

  const divider = "\x1b[90m" + "-".repeat(Math.min(cols, 67)) + "\x1b[0m";

  // Responsive Target Label
  const targetPrefix = `Target:    [${s.id}] `;
  const availTarget = Math.max(8, cols - targetPrefix.length);
  let safeTitle = s.title;
  if (s.parentTitle && cols >= 68) {
    const parentNote = ` (Parent: ${s.parentTitle})`;
    const availForTitle = Math.max(6, availTarget - parentNote.length);
    if (safeTitle.length > availForTitle) {
      safeTitle = safeTitle.slice(0, Math.max(1, availForTitle - 1)) + "…";
    }
    safeTitle = `${safeTitle} \x1b[90m${parentNote}\x1b[0m`;
  } else {
    if (safeTitle.length > availTarget) {
      safeTitle = safeTitle.slice(0, Math.max(1, availTarget - 1)) + "…";
    }
  }
  const targetLine = `Target:    \x1b[1;36m[${s.id}]\x1b[0m ${safeTitle}`;

  // Responsive Session Time Summary
  let sessionLine = "";
  if (cols >= 68) {
    sessionLine = `Session:   ${fmtTime(s.totalSec)} Total  |  Remaining: \x1b[1m${fmtTime(s.remainingSec)}\x1b[0m  |  Elapsed: ${fmtTime(s.elapsedSec)}`;
  } else if (cols >= 46) {
    sessionLine = `Session:   Rem: \x1b[1m${fmtTime(s.remainingSec)}\x1b[0m | Elapsed: ${fmtTime(s.elapsedSec)}`;
  } else {
    sessionLine = `Rem: \x1b[1m${fmtTime(s.remainingSec)}\x1b[0m (${fmtTime(s.totalSec)} tot)`;
  }

  const stepLabel = fmtStep(s.stepSec || 300);

  // Responsive Control Hints
  let controlLine = "";
  if (cols >= 85) {
    controlLine = `\x1b[2mControls:  [Space] Pause/Resume  |  [d] Complete & Exit  |  [+] +${stepLabel}  |  [-] -${stepLabel}  |  [q] Quit\x1b[0m`;
  } else if (cols >= 60) {
    controlLine = `\x1b[2m[Space] Pause  |  [d] Done  |  [+/-] ±${stepLabel}  |  [q] Quit\x1b[0m`;
  } else if (cols >= 40) {
    controlLine = `\x1b[2mSpace:Pause  d:Done  +/-:±${stepLabel}  q:Quit\x1b[0m`;
  } else {
    controlLine = `\x1b[2mSpace:Pause d:Done q:Quit\x1b[0m`;
  }

  const lines = [
    headerBanner,
    targetLine,
    sessionLine,
    "",
    `Progress:  [${bar}] ${pct.toFixed(cols < 42 ? 0 : 1)}%`,
    "",
    `Status:    ${stateBadge}`,
    divider,
    controlLine
  ];

  term.write(`\x1b[H${lines.join("\r\n")}\x1b[J`);
}

function startFocusInterval() {
  if (focusInterval) clearInterval(focusInterval);
  focusInterval = setInterval(() => {
    if (currentMode !== TerminalMode.FOCUS || !activeFocusSession) return;
    if (!activeFocusSession.isPaused) {
      activeFocusSession.elapsedSec++;
      activeFocusSession.remainingSec = Math.max(0, activeFocusSession.totalSec - activeFocusSession.elapsedSec);
      if (activeFocusSession.remainingSec === 0) {
        clearInterval(focusInterval);
        focusInterval = null;
        renderFocusSessionFrame();
        playTone("alarm");
        term.write("\r\n\r\n\x1b[1;32m[✔] FOCUS TIME ELAPSED! Press 'd' to mark done or 'q' to exit.\x1b[0m");
        return;
      }
    }
    renderFocusSessionFrame();
  }, 1000);
}

function enterFocusMode(payloadStr) {
  // Hard Reset: Cleanly cancel any existing interval and reset previous session state
  if (focusInterval) {
    clearInterval(focusInterval);
    focusInterval = null;
  }
  activeFocusSession = null;

  const data = typeof payloadStr === "string" ? JSON.parse(payloadStr) : payloadStr;

  if (data.is_fullscreen && document.documentElement.requestFullscreen) {
    document.documentElement.requestFullscreen().catch(() => {});
  }

  currentMode = TerminalMode.FOCUS;
  term.write("\x1b[?25l\x1b[2J\x1b[H"); // Hide cursor, clear screen

  const dur = Number(data.duration_sec) || 1500;
  const step = Number(data.step_sec) || (window.PyTodoBridge ? window.PyTodoBridge.getFocusStep() : 300);

  activeFocusSession = {
    id: String(data.id),
    title: String(data.title),
    parentTitle: String(data.parent_title || ""),
    totalSec: dur,
    remainingSec: dur,
    elapsedSec: 0,
    stepSec: step,
    isPaused: false,
    isFullscreen: Boolean(data.is_fullscreen)
  };

  renderFocusSessionFrame();
  startFocusInterval();
  updateMobileBarForMode(TerminalMode.FOCUS);
}

function exitFocusMode() {
  if (currentMode !== TerminalMode.FOCUS && !activeFocusSession) return;
  if (focusInterval) {
    clearInterval(focusInterval);
    focusInterval = null;
  }
  if (document.fullscreenElement && document.exitFullscreen) {
    document.exitFullscreen().catch(() => {});
  }
  activeFocusSession = null;
  currentMode = TerminalMode.SHELL;
  term.write("\x1b[?25h\x1b[2J\x1b[H"); // Restore cursor, clear screen
  updateMobileBarForMode(TerminalMode.SHELL);
  renderPrompt();
}

// --- 10. Bootstrap Pyodide & Mount Python Script ---
async function init() {
  try {
    term.writeln("\x1b[33m[*] Initializing PyTodo WebAssembly environment...\x1b[0m");
    pyodide = await loadPyodide();
    window.pyodide = pyodide;
    term.writeln("\x1b[33m[*] Loading PyTodo core engine...\x1b[0m");

    const pyCode = await fetch("main.py?v=" + Date.now()).then((res) => res.text());
    await pyodide.runPythonAsync(pyCode);

    term.writeln("\x1b[32m[✔] PyTodo CLI ready. Type 'help' for commands.\x1b[0m");
    renderPrompt();
    term.focus();

    // Initialize mobile quick-key accessory bar
    setupMobileBar();

    // Initial background sync check on boot
    debounceSync();
  } catch (err) {
    term.writeln(`\r\n\x1b[31m[✘] Fatal engine boot failure: ${err.message}\x1b[0m`);
    term.writeln("\x1b[90mEnsure your network connection allows loading WebAssembly from jsdelivr CDN.\x1b[0m");
  }
}
init();

// --- 11. VT100 Keystroke Parser & Shell State Machine ---
function setCommandLine(newText) {
  // Clear line from start of prompt
  term.write(`\r\x1b[K\x1b[1;36mtodo>\x1b[0m ${newText}`);
  inputBuffer = newText;
  cursorIndex = newText.length;
}

// Mobile Quick-Key Accessory Bar Setup & Mode Switching
function updateMobileBarForMode(mode) {
  const bar = document.getElementById("mobile-bar");
  if (!bar) return;
  if (mode === TerminalMode.FOCUS) {
    bar.innerHTML = `
      <button type="button" class="m-key" data-key=" ">Pause</button>
      <button type="button" class="m-key" data-key="d">Done</button>
      <button type="button" class="m-key" data-key="+">+5m</button>
      <button type="button" class="m-key" data-key="-">-5m</button>
      <button type="button" class="m-key" data-key="q">Exit</button>
    `;
  } else if (mode === TerminalMode.TOP) {
    bar.innerHTML = `
      <button type="button" class="m-key" data-key="q">Quit</button>
    `;
  } else {
    bar.innerHTML = `
      <button type="button" class="m-key" data-key="tab">Tab</button>
      <button type="button" class="m-key" data-key="esc">Esc</button>
      <button type="button" class="m-key" data-key="up">↑</button>
      <button type="button" class="m-key" data-key="down">↓</button>
      <button type="button" class="m-key" data-cmd="ls">ls</button>
      <button type="button" class="m-key" data-cmd="done ">done</button>
      <button type="button" class="m-key" data-cmd="add ">add</button>
      <button type="button" class="m-key" data-cmd="clear">clear</button>
    `;
  }
  setupMobileBar();
}

function setupMobileBar() {
  const bar = document.getElementById("mobile-bar");
  if (!bar) return;

  bar.querySelectorAll(".m-key").forEach((btn) => {
    const onTrigger = (e) => {
      e.preventDefault();
      unlockAudioGesture();
      const key = btn.getAttribute("data-key");
      const cmd = btn.getAttribute("data-cmd");

      if (key) {
        handleTerminalInput(key);
      } else if (cmd) {
        if (cmd.endsWith(" ")) {
          if (!inputBuffer.trim()) {
            setCommandLine(cmd);
          } else {
            setCommandLine(inputBuffer.trimEnd() + " " + cmd.trimStart());
          }
          term.focus();
        } else {
          setCommandLine(cmd);
          handleTerminalInput("\r");
        }
      }
    };

    btn.addEventListener("pointerdown", onTrigger);
  });
}

async function handleTerminalInput(data) {
  unlockAudioGesture();

  // Mode A: HTOP Dashboard Mode Key Handling
  if (currentMode === TerminalMode.TOP) {
    if (data === "q" || data === "Q" || data === "\x1b" || data === "\x03") {
      exitTopDashboard();
    }
    return;
  }

  // Mode A2: FOCUS Mode Key Handling
  if (currentMode === TerminalMode.FOCUS) {
    if (data === " " || data === "p" || data === "P") {
      if (activeFocusSession) {
        activeFocusSession.isPaused = !activeFocusSession.isPaused;
        playTone("click");
        renderFocusSessionFrame();
      }
      return;
    }
    if (data === "d" || data === "D") {
      if (activeFocusSession && pyodide) {
        const tid = activeFocusSession.id;
        exitFocusMode();
        try {
          const res = await pyodide.runPythonAsync(`cli_done([${JSON.stringify(tid)}])`);
          term.writeln(`\r\n${res.replace(/\n/g, "\r\n")}`);
          term.writeln("\x1b[1;32m[★] Focus session completed triumphantly!\x1b[0m");
          playTone("done");
        } catch (e) {
          term.writeln(`\r\nError completing task: ${e.message}`);
        }
        renderPrompt();
      }
      return;
    }
    if (data === "+" || data === "=") {
      const now = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
      if (now - lastTimerAdjustTime < 180) return;
      lastTimerAdjustTime = now;

      if (activeFocusSession) {
        const step = activeFocusSession.stepSec || 300;
        activeFocusSession.totalSec += step;
        activeFocusSession.remainingSec += step;
        playTone("step_up");
        if (!focusInterval && !activeFocusSession.isPaused && activeFocusSession.remainingSec > 0) {
          startFocusInterval();
        }
        renderFocusSessionFrame();
      }
      return;
    }
    if (data === "-" || data === "_") {
      const now = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
      if (now - lastTimerAdjustTime < 180) return;
      lastTimerAdjustTime = now;

      if (activeFocusSession) {
        const step = activeFocusSession.stepSec || 300;
        const maxDeduct = Math.max(0, activeFocusSession.remainingSec - 5);
        const actualDeduct = Math.min(step, maxDeduct);
        if (actualDeduct > 0) {
          activeFocusSession.remainingSec -= actualDeduct;
          activeFocusSession.totalSec = Math.max(
            activeFocusSession.elapsedSec + activeFocusSession.remainingSec,
            activeFocusSession.totalSec - actualDeduct
          );
          playTone("step_down");
          renderFocusSessionFrame();
        }
      }
      return;
    }
    if (data === "q" || data === "Q" || data === "\x1b" || data === "\x03") {
      exitFocusMode();
      return;
    }
    return;
  }

  if (!pyodide) return;

  // Mode B: Shell REPL Mode Key Handling

  // 1. Arrow Keys
  // Up Arrow: \x1b[A
  if (data === "\x1b[A") {
    if (commandHistory.length > 0) {
      if (historyIndex === -1) {
        draftBuffer = inputBuffer;
        historyIndex = commandHistory.length - 1;
      } else if (historyIndex > 0) {
        historyIndex--;
      }
      setCommandLine(commandHistory[historyIndex]);
    }
    return;
  }

  // Down Arrow: \x1b[B
  if (data === "\x1b[B") {
    if (historyIndex !== -1) {
      if (historyIndex < commandHistory.length - 1) {
        historyIndex++;
        setCommandLine(commandHistory[historyIndex]);
      } else {
        historyIndex = -1;
        setCommandLine(draftBuffer);
      }
    }
    return;
  }

  // Left Arrow: \x1b[D
  if (data === "\x1b[D") {
    if (cursorIndex > 0) {
      cursorIndex--;
      term.write("\x1b[D");
    }
    return;
  }

  // Right Arrow: \x1b[C
  if (data === "\x1b[C") {
    if (cursorIndex < inputBuffer.length) {
      cursorIndex++;
      term.write("\x1b[C");
    }
    return;
  }

  // 2. Tab Autocompletion: \t (\x09)
  if (data === "\t") {
    try {
      const escaped = JSON.stringify(inputBuffer);
      const resRaw = await pyodide.runPythonAsync(`get_autocomplete_suggestions(${escaped})`);
      const matches = JSON.parse(resRaw);

      if (matches.length === 1) {
        // Single match -> Complete inline
        const completedWord = matches[0];
        const beforeCursor = inputBuffer.slice(0, cursorIndex);
        const afterCursor = inputBuffer.slice(cursorIndex);
        const tokens = beforeCursor.trimStart().split(/\s+/);
        if (tokens.length <= 1) {
          setCommandLine(completedWord + " " + afterCursor.trimStart());
        } else {
          tokens[tokens.length - 1] = completedWord;
          const newBefore = (beforeCursor.startsWith(" ") ? " " : "") + tokens.join(" ") + " ";
          setCommandLine(newBefore + afterCursor.trimStart());
        }
      } else if (matches.length > 1) {
        // Multiple matches -> Print candidates and restore prompt
        term.writeln(`\r\n\x1b[90m${matches.join("   ")}\x1b[0m`);
        renderPrompt();
        term.write(inputBuffer);
        if (cursorIndex < inputBuffer.length) {
          term.write(`\x1b[${inputBuffer.length - cursorIndex}D`);
        }
      }
    } catch (e) {
      // Ignore tab errors
    }
    return;
  }

  // 3. Ctrl+C: Cancel active buffer (\x03)
  if (data === "\x03") {
    inputBuffer = "";
    cursorIndex = 0;
    historyIndex = -1;
    term.writeln("^C");
    renderPrompt();
    return;
  }

  // 4. Ctrl+L: Clear screen (\x0c)
  if (data === "\x0c") {
    term.clear();
    renderPrompt();
    term.write(inputBuffer);
    return;
  }

  // 5. Backspace: \u007F or \b (with surrogate pair & wide-character clean redraw)
  if (data === "\u007F" || data === "\b") {
    if (cursorIndex > 0) {
      let delCount = 1;
      if (cursorIndex >= 2) {
        const prevCode = inputBuffer.charCodeAt(cursorIndex - 1);
        const leadingCode = inputBuffer.charCodeAt(cursorIndex - 2);
        if (prevCode >= 0xDC00 && prevCode <= 0xDFFF && leadingCode >= 0xD800 && leadingCode <= 0xDBFF) {
          delCount = 2;
        }
      }
      inputBuffer = inputBuffer.slice(0, cursorIndex - delCount) + inputBuffer.slice(cursorIndex);
      cursorIndex -= delCount;

      term.write("\r\x1b[K\x1b[1;36mtodo>\x1b[0m " + inputBuffer);
      if (cursorIndex < inputBuffer.length) {
        const backCount = inputBuffer.length - cursorIndex;
        term.write(`\x1b[${backCount}D`);
      }
    }
    return;
  }

  // 6. Enter Key: \r (protected by isCommandRunning mutex)
  if (data === "\r") {
    if (isCommandRunning) return;
    term.writeln("");
    const command = inputBuffer.trim();
    inputBuffer = "";
    cursorIndex = 0;
    historyIndex = -1;

    if (command.length > 0) {
      // Append to history if not duplicate of last command
      if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== command) {
        commandHistory.push(command);
      }

      isCommandRunning = true;
      try {
        const escaped = JSON.stringify(command);
        const result = await pyodide.runPythonAsync(`handle_command(${escaped})`);
        if (result === "__CLEAR_SCREEN__") {
          term.clear();
        } else if (result) {
          term.writeln(result.replace(/\n/g, "\r\n"));
        }
      } catch (err) {
        term.writeln(`\x1b[31mExecution error: ${err.message}\x1b[0m`);
        playTone("fail");
      } finally {
        isCommandRunning = false;
      }
    }

    if (currentMode === TerminalMode.SHELL) {
      renderPrompt();
    }
    return;
  }

  // 7. Printable Characters & Multi-character Pastes (sanitizes embedded newlines)
  if (!data.startsWith("\x1b") && data !== "\r" && data !== "\n") {
    const sanitized = data.replace(/[\r\n]+/g, " ");
    if (sanitized.length > 0) {
      inputBuffer = inputBuffer.slice(0, cursorIndex) + sanitized + inputBuffer.slice(cursorIndex);
      cursorIndex += sanitized.length;
      term.write(sanitized);
      if (cursorIndex < inputBuffer.length) {
        term.write(inputBuffer.slice(cursorIndex));
        term.write(`\x1b[${inputBuffer.length - cursorIndex}D`);
      }
    }
  }
}
term.onData(handleTerminalInput);

// --- 12. Service Worker Registration ---
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    try {
      const swUrl = new URL("sw.js", window.location.href).href;
      navigator.serviceWorker.register(swUrl, { scope: "./" }).catch((err) => {
        console.warn("[SW] Registration skipped:", err);
      });
    } catch (e) {
      console.warn("[SW] Registration error:", e);
    }
  });
}
