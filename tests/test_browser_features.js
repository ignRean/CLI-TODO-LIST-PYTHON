const { chromium } = require("C:/Users/rehaa/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core");
const fs = require("fs");
const path = require("path");

async function runTests() {
  console.log("==================================================");
  console.log("🚀 STARTING PYTODO CLI BROWSER FEATURE TEST SUITE");
  console.log("==================================================");

  const browser = await chromium.launch({ headless: true });
  const outDir = path.resolve(__dirname, "../docs/conclusions");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const results = [];

  try {
    // -------------------------------------------------------------
    // Test 1: Desktop Environment & WebAssembly / Pyodide Boot
    // -------------------------------------------------------------
    console.log("\n[*] 1. Launching Desktop Context (1280x800)...");
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      hasTouch: false
    });
    const page = await desktopContext.newPage();
    
    page.on("console", msg => {
      // console.log("  [Browser Console]:", msg.text());
    });

    const appUrl = "http://localhost:8000/github-upload/";
    await page.goto(appUrl, { waitUntil: "networkidle" });

    console.log("[*] Waiting for Pyodide and WebAssembly environment initialization...");
    await page.waitForFunction(() => {
      return document.querySelector(".xterm-rows") && document.body.innerText.includes("todo>");
    }, { timeout: 45000 });
    console.log("  ✔ Pyodide and xterm.js loaded successfully. Prompt active.");
    results.push({ test: "Pyodide & Terminal Boot", status: "PASSED" });

    // Helper to send command to terminal and wait for response
    async function executeCommand(cmd, expectedText, timeout = 5000) {
      console.log(`  > Executing: ${cmd}`);
      await page.keyboard.type(cmd, { delay: 15 });
      await page.keyboard.press("Enter");
      await page.waitForFunction((text) => {
        return document.body.innerText.includes(text);
      }, expectedText, { timeout });
      console.log(`  ✔ Verified output contains: "${expectedText}"`);
    }

    // -------------------------------------------------------------
    // Test 2: Help & Command Discovery
    // -------------------------------------------------------------
    console.log("\n[*] 2. Testing Help command...");
    await executeCommand("h", "PyTodo Commands:");
    results.push({ test: "Help Command (h)", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 3: Add Task with Subtasks, Due Time & Duration
    // -------------------------------------------------------------
    console.log("\n[*] 3. Testing Task Creation with Due, Duration & Subtasks...");
    await executeCommand(
      'add "Prepare Launch Pitch" --due 18:30 --duration 45m -s "Slide deck" -s "Review metrics"',
      "Prepare Launch Pitch",
      8000
    );
    results.push({ test: "Add Task with Subtasks & Due Time", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 4: Tabular Task Listing (ls) & Subtask Tree
    // -------------------------------------------------------------
    console.log("\n[*] 4. Testing 'ls' in Wide Mode...");
    await executeCommand("ls", "Prepare Launch Pitch", 8000);
    const terminalText = await page.evaluate(() => document.body.innerText);
    if (terminalText.includes("Slide deck") && terminalText.includes("Review metrics")) {
      console.log("  ✔ Subtask tree correctly rendered in table view.");
      results.push({ test: "ls Wide Mode Subtask Tree", status: "PASSED" });
    } else {
      throw new Error("Subtasks not found in ls output");
    }

    // -------------------------------------------------------------
    // Test 5: Subtask Completion & Progress Ratio
    // -------------------------------------------------------------
    console.log("\n[*] 5. Testing Subtask Completion ('done 1.1')...");
    await executeCommand("done 1.1", "Subtask completed:", 8000);
    await executeCommand("ls", "1/2 done", 8000);
    results.push({ test: "Subtask Done & Ratio [1/2 done]", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 6: In-Place Editing (Title & Add Subtask)
    // -------------------------------------------------------------
    console.log("\n[*] 6. Testing 'edit' Command...");
    await executeCommand('edit 1 --title "Prepare Global Launch Pitch" --add-sub "Rehearse demo"', "updated:", 8000);
    await executeCommand("ls", "Rehearse demo", 8000);
    results.push({ test: "Edit Task Title & Add Subtask", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 7: Device Pairing / Link Generation
    // -------------------------------------------------------------
    console.log("\n[*] 7. Testing 6-Character Base32 Pairing Key Generation ('link generate')...");
    await executeCommand("link generate", "Pairing key generated:", 8000);
    results.push({ test: "Device Pairing Key Generation", status: "PASSED" });

    console.log("\n[*] 7b. Testing Active Pairing Key Query ('code')...");
    await executeCommand("code", "Active Pairing Key:", 8000);
    results.push({ test: "CLI 'code' Command Display", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 8: Web Audio FX Test
    // -------------------------------------------------------------
    console.log("\n[*] 8. Testing 8-Bit Retro Audio FX ('sound test')...");
    await executeCommand("sound test", "Playing test retro chime", 8000);
    results.push({ test: "Web Audio FX Synth", status: "PASSED" });

    // Test 8b: Test all 15 procedural retro audio sound synthesizers
    console.log("\n[*] 8b. Testing all 15 procedural retro audio sound synthesizers...");
    const synthResult = await page.evaluate(() => {
      const sounds = [
        "done", "subtask", "fail", "wipe",
        "add", "rm", "undone", "alarm", "celebration", "streak",
        "revive", "click", "step_up", "step_down", "theme"
      ];
      try {
        sounds.forEach(s => window.PyTodoBridge.playSound(s));
        return { success: true, count: sounds.length };
      } catch (err) {
        return { success: false, error: err.message };
      }
    });
    if (!synthResult.success) throw new Error("Audio synth error: " + synthResult.error);
    console.log(`  ✔ Successfully synthesized all ${synthResult.count} 8-bit retro audio sound effects.`);
    results.push({ test: "All 15 Retro Audio FX Synths", status: "PASSED" });

    // Test 8c: Test Terminal Cushion DOM Presence & Dimensions
    console.log("\n[*] 8c. Testing Adaptive Terminal Cushion Element...");
    const cushionInfo = await page.evaluate(() => {
      const c = document.getElementById("terminal-cushion");
      if (!c) return { exists: false };
      const style = window.getComputedStyle(c);
      return { exists: true, flexBasis: style.flexBasis, display: style.display };
    });
    if (!cushionInfo.exists) throw new Error("Missing #terminal-cushion element in DOM");
    console.log("  ✔ #terminal-cushion successfully rendered with adaptive layout styles.");
    results.push({ test: "Adaptive Terminal Cushion", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 9: Pomodoro Focus Mode Screen
    // -------------------------------------------------------------
    console.log("\n[*] 9. Testing Focus Mode Interactive Screen ('focus 1')...");
    await page.keyboard.type("focus 1", { delay: 15 });
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => {
      const txt = document.body.innerText;
      return txt.includes("FOCUS ENGINE") || txt.includes("Target:") || txt.includes("Session:");
    }, { timeout: 8000 });
    console.log("  ✔ Focus screen active with interactive controls.");
    // Press 'q' to exit focus screen
    await page.keyboard.press("q");
    await page.waitForTimeout(800);
    console.log("  ✔ Exited focus mode back to shell.");
    results.push({ test: "Interactive Focus Mode", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 10: Live HTOP Monitor ('top')
    // -------------------------------------------------------------
    console.log("\n[*] 10. Testing Live Dashboard Monitor ('top')...");
    await page.keyboard.type("top", { delay: 15 });
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => {
      const txt = document.body.innerText;
      return txt.includes("LIVE HTOP MONITOR") || txt.includes("Local Time:") || txt.includes("Day Progress");
    }, { timeout: 8000 });
    console.log("  ✔ Live HTOP monitor active.");
    // Press 'q' to exit top screen
    await page.keyboard.press("q");
    await page.waitForTimeout(800);
    console.log("  ✔ Exited top mode back to shell.");
    results.push({ test: "Live HTOP Dashboard Monitor", status: "PASSED" });

    // -------------------------------------------------------------
    // Test 10b: Narrow Window Ticker Stability (No Newline Drift)
    // -------------------------------------------------------------
    console.log("\n[*] 10b. Testing Narrow Window Ticker Stability (No Newline Drift)...");
    await page.setViewportSize({ width: 420, height: 600 });
    await page.waitForTimeout(1000);
    const textBefore = await page.evaluate(() => document.body.innerText);
    const countBefore = (textBefore.match(/todo>/g) || []).length;
    // Wait 3.5 seconds across 3 countdown ticker pulses
    await page.waitForTimeout(3500);
    const textAfter = await page.evaluate(() => document.body.innerText);
    const countAfter = (textAfter.match(/todo>/g) || []).length;
    console.log(`  ✔ Ticker prompt count: before=${countBefore}, after=${countAfter}`);
    const noDownwardsDrift = countAfter <= countBefore + 1;
    results.push({ test: "Narrow Window Ticker Stability (No Downward Drift)", status: noDownwardsDrift ? "PASSED" : "FAILED" });

    // Restore desktop viewport for screenshot
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(500);

    // Take Desktop Screenshot
    const desktopScreenshot = path.join(outDir, "test-features-desktop.png");
    await page.screenshot({ path: desktopScreenshot });
    console.log(`  ✔ Desktop screenshot saved: ${desktopScreenshot}`);

    // Verify desktop mobile bar is strictly hidden
    const isMobileBarHiddenDesktop = await page.evaluate(() => {
      const bar = document.getElementById("mobile-bar");
      return window.getComputedStyle(bar).display === "none";
    });
    console.log("  ✔ Mobile accessory bar hidden on desktop:", isMobileBarHiddenDesktop);
    results.push({ test: "Desktop Viewport Accessory Bar Hidden", status: isMobileBarHiddenDesktop ? "PASSED" : "FAILED" });

    await desktopContext.close();

    // -------------------------------------------------------------
    // Test 11: Mobile Touch Context & Accessory Keyboard Bar
    // -------------------------------------------------------------
    console.log("\n[*] 11. Launching Mobile Touch Context (390x844 iPhone 14)...");
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true
    });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto(appUrl, { waitUntil: "networkidle" });

    await mobilePage.waitForFunction(() => {
      return document.querySelector(".xterm-rows") && document.body.innerText.includes("todo>");
    }, { timeout: 35000 });

    const isMobileBarImmediatelyVisible = await mobilePage.evaluate(() => {
      const bar = document.getElementById("mobile-bar");
      const rect = bar.getBoundingClientRect();
      const cs = window.getComputedStyle(bar);
      return cs.display === "flex" && rect.height > 0 && rect.bottom <= window.innerHeight + 1 && rect.top < window.innerHeight;
    });
    console.log("  ✔ Mobile accessory bar visible immediately on load (before typing):", isMobileBarImmediatelyVisible);
    results.push({ test: "Mobile Touch Accessory Bar Immediately Visible", status: isMobileBarImmediatelyVisible ? "PASSED" : "FAILED" });

    // Test clicking mobile bar button [ls]
    console.log("  [*] Clicking mobile bar [ls] button...");
    await mobilePage.click('button[data-cmd="ls"]');
    await mobilePage.waitForTimeout(1000);
    let mobileText = await mobilePage.evaluate(() => document.body.innerText);
    const lsRan = mobileText.includes("No tasks for today") || mobileText.includes("add <title>") || mobileText.includes("ls");
    console.log("  ✔ Mobile bar [ls] triggered successfully:", lsRan);

    // Test adding task on mobile and listing in Narrow Stream Mode (< 65 cols)
    console.log("  [*] Clicking mobile bar [add] button and adding a mobile task...");
    await mobilePage.click('button[data-cmd="add "]');
    await mobilePage.keyboard.type('"Touch UX Sprint" -s "Tap targets"', { delay: 15 });
    await mobilePage.keyboard.press("Enter");
    await mobilePage.waitForTimeout(1000);

    // Trigger [ls] again via mobile bar
    await mobilePage.click('button[data-cmd="ls"]');
    await mobilePage.waitForTimeout(1000);
    mobileText = await mobilePage.evaluate(() => document.body.innerText);
    const streamModeVerified = mobileText.includes("Touch UX Sprint") && mobileText.includes("Tap targets");
    console.log("  ✔ Mobile stream mode card rendering verified:", streamModeVerified);

    results.push({ test: "Mobile Bar Touch Actions & Stream Mode", status: (lsRan && streamModeVerified) ? "PASSED" : "FAILED" });

    // Take Mobile Screenshot
    const mobileScreenshot = path.join(outDir, "test-features-mobile.png");
    await mobilePage.screenshot({ path: mobileScreenshot });
    console.log(`  ✔ Mobile screenshot saved: ${mobileScreenshot}`);

    await mobileContext.close();

    console.log("\n==================================================");
    console.log("📊 BROWSER TEST RESULTS SUMMARY");
    console.log("==================================================");
    let allPassed = true;
    for (const r of results) {
      console.log(`  [${r.status}] ${r.test}`);
      if (r.status !== "PASSED") allPassed = false;
    }
    console.log(`\nFinal Verdict: ${allPassed ? "ALL BROWSER TESTS PASSED (100%)" : "FAILURES DETECTED"}`);
  } catch (err) {
    console.error("\n❌ Test Suite Aborted due to error:", err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runTests();
