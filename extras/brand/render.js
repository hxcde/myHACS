// Renders the brand SVGs to PNG with transparent background.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const out = process.argv[2];
const icon = fs.readFileSync(path.join(__dirname, "icon.svg"), "utf8");
const inner = icon.replace(/^<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "");

function logo(textColor) {
  // icon (height 200) + wordmark, rendered large and trimmed afterwards
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="240" viewBox="0 0 1000 240">
    <svg x="0" y="20" width="200" height="200" viewBox="18 20 220 220">${inner}</svg>
    <text x="210" y="168" font-family="Inter Display, Inter, sans-serif" font-weight="700" font-size="150"
          letter-spacing="-3" fill="${textColor}">Bastion</text>
  </svg>`;
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  const jobs = [
    ["icon_src.png", icon.replace('width="256" height="256"', 'width="1024" height="1024"'), 1024, 1024],
    ["logo_src.png", logo("#14243a"), 1000, 240],
    ["dark_logo_src.png", logo("#eef3fa"), 1000, 240],
  ];
  for (const [name, svg, w, h] of jobs) {
    await page.setViewportSize({ width: w, height: h });
    await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    await page.waitForTimeout(150);
    await page.screenshot({ path: path.join(out, name), omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
  }
  await browser.close();
})();
