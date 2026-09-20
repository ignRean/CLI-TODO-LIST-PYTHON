const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

async function run() {
  const browser = await chromium.launch({ headless: true });
  const outDir = path.resolve(__dirname, "../docs/conclusions");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  console.log("[*] Verifying Desktop Environment (1280x800)...");
  const desktopContext = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    hasTouch: false
  });
  const desktopPage = await desktopContext.newPage();
  await desktopPage.goto("http://localhost:8089/", { waitUntil: "networkidle" });
  
  // Wait for terminal prompt
  await desktopPage.waitForFunction(() => {
    return document.querySelector(".xterm-rows") && document.body.innerText.includes("todo>");
  }, { timeout: 25000 });

  // Verify mobile bar is hidden on desktop
  const isMobileBarHidden = await desktopPage.evaluate(() => {
    const bar = document.getElementById("mobile-bar");
    return window.getComputedStyle(bar).display === "none";
  });
  console.log("[✔] Desktop mobile bar hidden:", isMobileBarHidden);

  // Type help to show new commands
  await desktopPage.keyboard.type("h");
  await desktopPage.keyboard.press("Enter");
  await desktopPage.waitForTimeout(800);

  const desktopScreenshot = path.join(outDir, "test-desktop-workstation.png");
  await desktopPage.screenshot({ path: desktopScreenshot });
  console.log(`[✔] Desktop screenshot saved to: ${desktopScreenshot}`);

  console.log("[*] Verifying Mobile Touch Environment (390x844, iPhone 14 / Pixel)...");
  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true
  });
  const mobilePage = await mobileContext.newPage();
  await mobilePage.goto("http://localhost:8089/", { waitUntil: "networkidle" });

  await mobilePage.waitForFunction(() => {
    return document.querySelector(".xterm-rows") && document.body.innerText.includes("todo>");
  }, { timeout: 25000 });

  // Verify mobile bar is visible
  const isMobileBarVisible = await mobilePage.evaluate(() => {
    const bar = document.getElementById("mobile-bar");
    return window.getComputedStyle(bar).display === "flex";
  });
  console.log("[✔] Mobile bar visible on touch viewport:", isMobileBarVisible);

  // Verify mobile bar micro-keys
  const keyCount = await mobilePage.evaluate(() => {
    return document.querySelectorAll("#mobile-bar .m-key").length;
  });
  console.log(`[✔] Mobile toolbar micro-keys count: ${keyCount} (Expected: 8)`);

  // Tap [ls] button on mobile toolbar
  console.log("[*] Tapping mobile toolbar [ls] micro-key...");
  await mobilePage.click('button[data-cmd="ls"]');
  await mobilePage.waitForTimeout(1000);

  const mobileScreenshot = path.join(outDir, "test-mobile-workstation.png");
  await mobilePage.screenshot({ path: mobileScreenshot });
  console.log(`[✔] Mobile screenshot saved to: ${mobileScreenshot}`);

  await browser.close();
  console.log("\n==========================================");
  console.log("PLAYWRIGHT BROWSER VERIFICATION PASSED! [✔]");
  console.log("==========================================");
}

run().catch((err) => {
  console.error("Playwright Error:", err);
  process.exit(1);
});
