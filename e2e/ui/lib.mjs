import { chromium, devices } from "playwright";
export const EXE = process.env.HOME + "/Library/Caches/ms-playwright/chromium_headless_shell-1255/chrome-headless-shell-mac-arm64/chrome-headless-shell";
export const FE = process.env.FE || "http://localhost:3100";
export async function open() {
  const browser = await chromium.launch({ executablePath: EXE });
  const ctx = await browser.newContext({ ...devices["Pixel 7"], locale: "en-US" });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message.slice(0, 200)));
  page.on("console", (m) => { if (m.type() === "error") console.log("CONSOLE.ERROR", m.text().slice(0, 200)); });
  return { browser, ctx, page };
}
export async function controls(page) {
  return page.evaluate(() => [...document.querySelectorAll("button,a,input,textarea,select")].filter(e => e.offsetParent !== null).map(e => (e.tagName + ":" + (e.innerText || e.placeholder || e.getAttribute("aria-label") || e.value || e.type || "")).replace(/\s+/g, " ").slice(0, 70)));
}
