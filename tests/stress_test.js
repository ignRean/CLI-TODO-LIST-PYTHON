const { chromium } = require("C:/Users/rehaa/AppData/Roaming/npm/node_modules/@playwright/cli/node_modules/playwright-core");
const fs = require("fs");
const path = require("path");

async function runStressTests() {
  console.log("=== STARTING PLAYWRIGHT FAULT INJECTION & INTEGRATION SUITE ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const consoleWarns = [];
  page.on("console", msg => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
    if (msg.type() === "warning") consoleWarns.push(msg.text());
  });
  page.on("pageerror", err => {
    consoleErrors.push(`[PAGE ERROR]: ${err.message}`);
  });

  console.log("[1] Navigating to http://localhost:8089/...");
  await page.goto("http://localhost:8089/", { waitUntil: "networkidle" });

  console.log("[2] Waiting for Pyodide & Terminal prompt...");
  try {
    await page.waitForFunction(() => {
      return document.querySelector(".xterm-rows") && document.body.innerText.includes("todo>");
    }, { timeout: 35000 });
    console.log("    [✔] Boot completed successfully! Terminal prompt found.");
  } catch (e) {
    console.error("    [✘] Boot timed out or failed to reach prompt:", e.message);
    console.log("    Console errors:", consoleErrors);
    await browser.close();
    process.exit(1);
  }

  // Helper to send command to xterm and wait for next prompt
  async function executeCliCommand(cmd, waitMs = 1200) {
    // Type command
    await page.keyboard.type(cmd, { delay: 10 });
    await page.keyboard.press("Enter");
    await page.waitForTimeout(waitMs);
    const text = await page.evaluate(() => document.querySelector(".xterm-rows")?.innerText || "");
    return text;
  }

  // Helper to evaluate Python state directly via Pyodide
  async function pyEval(code) {
    return await page.evaluate((c) => {
      try {
        const res = window.pyodide.runPython(c);
        return { success: true, result: String(res) };
      } catch (err) {
        return { success: false, error: String(err) };
      }
    }, code);
  }

  console.log("\n[3] Testing Basic Commands & Help...");
  let out = await executeCliCommand("help");
  console.log("    help executed, response length:", out.length);

  console.log("\n[4] Testing Task Creation, Listing & Subtasks...");
  await executeCliCommand("add \"Finish PhD Security Audit\" --due 18:00 --dur 45");
  await executeCliCommand("ls");
  let tasks = await pyEval("[t['title'] for t in get_local_todos()]");
  console.log("    Active tasks in Python:", tasks);

  console.log("\n[5] Fault Injection: Extreme Character Length (Fuzzing title)...");
  const longTitle = "A".repeat(1200);
  await executeCliCommand(`add "${longTitle}"`);
  tasks = await pyEval("len(get_local_todos())");
  console.log("    Task count after 1200-char add:", tasks);

  console.log("\n[6] Fault Injection: ANSI Injection & Terminal Escape sequences...");
  const maliciousAnsi = "\\x1b[31;1mHACKED\\x1b[0m; rm -rf /; <script>alert(1)</script>";
  await executeCliCommand(`add "${maliciousAnsi}"`);
  let lastTask = await pyEval("get_local_todos()[-1]['title']");
  console.log("    Stored title for ANSI injection:", JSON.stringify(lastTask));

  console.log("\n[7] Fault Injection: Subtask deep stress & out-of-bounds...");
  let invalidSub = await executeCliCommand("subtask add 99999 \"Nonexistent parent\"");
  console.log("    Output for invalid parent subtask add (should not crash):", invalidSub.slice(-150));

  console.log("\n[8] Testing Pairing Code Generation & Supabase sync status...");
  let pairStatus = await executeCliCommand("pair status");
  console.log("    Pair status output:", pairStatus.slice(-250));

  console.log("\n[9] Fault Injection: Malformed Theme command...");
  await executeCliCommand("theme nonexistent_theme_foo");
  await executeCliCommand("theme matrix");
  let curTheme = await page.evaluate(() => localStorage.getItem("py_todo_theme"));
  console.log("    Local storage theme after switching to matrix:", curTheme);

  console.log("\n[10] Fault Injection: Network Disconnection during Sync...");
  await context.setOffline(true);
  console.log("    Network set to OFFLINE.");
  await executeCliCommand("add \"Offline Created Task\" --due 20:00");
  await executeCliCommand("done 1");
  await executeCliCommand("pair sync");
  console.log("    Offline command executed without uncaught exception.");
  
  await context.setOffline(false);
  console.log("    Network restored to ONLINE.");
  await page.waitForTimeout(2000);
  await executeCliCommand("pair sync");

  console.log("\n[11] Checking Captured Browser Console Errors:");
  if (consoleErrors.length === 0) {
    console.log("    [✔] Zero unhandled browser console errors detected!");
  } else {
    console.log(`    [!] ${consoleErrors.length} Console errors detected:`);
    consoleErrors.forEach((err, idx) => console.log(`       (${idx + 1}) ${err}`));
  }

  await browser.close();
  console.log("\n=== PLAYWRIGHT FAULT SUITE COMPLETE ===");
}

runStressTests().catch(err => {
  console.error("FATAL ERROR IN SUITE:", err);
  process.exit(1);
});
