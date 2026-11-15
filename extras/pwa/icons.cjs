const { chromium } = require("playwright");
// Shield with keyhole on the Argus blue; "any" = rounded tile, maskable/apple = full bleed with safe zone.
const shield = (scale) => `<g transform="translate(256 256) scale(${scale}) translate(-16 -16)">
  <path d="M16 2.5 4.5 7v8.2c0 7 4.9 13.2 11.5 14.8 6.6-1.6 11.5-7.8 11.5-14.8V7L16 2.5Z" fill="#fff"/>
  <circle cx="16" cy="13.8" r="2.7" fill="#006fff"/><path d="M14.7 15.2h2.6l.9 5.6h-4.4l.9-5.6Z" fill="#006fff"/></g>`;
const bg = '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2b86ff"/><stop offset="1" stop-color="#0059d6"/></linearGradient></defs>';
const variants = {
  "icon-any": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">${bg}<rect x="16" y="16" width="480" height="480" rx="112" fill="url(#g)"/>${shield(9.6)}</svg>`,
  "icon-maskable": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">${bg}<rect width="512" height="512" fill="url(#g)"/>${shield(7.4)}</svg>`,
  "icon-apple": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">${bg}<rect width="512" height="512" fill="url(#g)"/>${shield(8.6)}</svg>`,
};
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  const out = {};
  for (const [name, svg] of Object.entries(variants)) {
    for (const size of name === "icon-any" ? [192, 512] : name === "icon-apple" ? [180] : [512]) {
      await p.setViewportSize({ width: size, height: size });
      await p.setContent(`<html><body style="margin:0;background:transparent">${svg.replace("<svg ", `<svg width="${size}" height="${size}" `)}</body></html>`);
      const file = `${name}-${size}.png`;
      await p.screenshot({ path: file, omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
      out[file] = true;
    }
  }
  require("fs").writeFileSync("favicon.svg", variants["icon-any"]);
  console.log(Object.keys(out));
  await b.close();
})();
