// One year as one photographic frame. A slit sweeps left to right like a
// slit-scan camera: every working day exposes as smeared light, public
// projects come out sharp with name, language and numbers.
//
// GitHub serves README images through camo as <img>, so: no JS, no external
// fonts, CSS animations only, and the final state must be the resting state
// so reduced-motion and static renderers show a complete picture.
//
// Two frames share everything but layout: "wide" for desktop, "tall" for
// phones (the README picks one with <picture media>).

import type { Data, Project } from "./fetch.ts";

export type Notes = Record<string, string>;
export type Fonts = { regular: string; bold: string };
export type Layout = "wide" | "tall";

const C = {
  bg: "#13100c",
  film: "#0d0b08",
  rule: "#2b241b",
  paper: "#efdfbd",
  muted: "#b59969",
  quiet: "#7d6c55",
  dim: "#3b3228",
  core: "#ffe6b8",
  warm: "#e2a964",
  ember: "#a8643a",
  accent: "#ffc97a",
};

const LANG: Record<string, string> = {
  Rust: "#e2a964",
  TypeScript: "#efdfbd",
  "C++": "#c98a55",
  JavaScript: "#d8c49d",
  Python: "#b59969",
};

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const SWEEP = 5.2; // seconds for the slit to cross the frame
const DELAY = 0.4;

const esc = (s: string | number) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const num = (n: number) => n.toLocaleString("en-US").replace(/,/g, " ");
const f = (n: number) => +n.toFixed(2);
const dayIndex = (from: string, d: string) => Math.round((Date.parse(d) - Date.parse(from)) / 86400e3);
const human = (d: string) => {
  const t = new Date(d + "T00:00:00Z");
  return `${t.getUTCDate()} ${MONTHS[t.getUTCMonth()]} ${t.getUTCFullYear()}`;
};
// Monospace advance of JetBrains Mono is 0.6em; good enough for layout math.
const textW = (s: string, size: number) => s.length * size * 0.6;
// A full space between digit groups is too wide in a monospace face and the
// subset has no thin space, so groups are nudged apart with dx instead.
const big = (n: number) =>
  String(n).replace(/\B(?=(\d{3})+$)/g, "|").split("|")
    .map((g, i) => (i ? `<tspan dx="4">${g}</tspan>` : g)).join("");

type Lane = {
  p: Project;
  first: string;
  last: string;
  title: string;
  meta: string;
  note: string;
  color: string;
  weight: number;
};

function model(data: Data, notes: Notes) {
  const days = data.days;
  let longest = 0, run = 0;
  for (const d of days) {
    run = d.count > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
  }
  const peak = days.reduce((a, b) => (b.count > a.count ? b : a));
  const active = days.filter((d) => d.count > 0).length;

  // Densest 28-day stretch; the private annotation points there.
  let best = 0, bestAt = 0, acc = 0;
  days.forEach((d, i) => {
    acc += d.count - (i >= 28 ? days[i - 28].count : 0);
    if (acc > best) { best = acc; bestAt = i - 27; }
  });

  const lanes: Lane[] = data.projects
    .map((p) => {
      const dates = [...Object.keys(p.commits), ...p.prs.map((x) => x.date)].sort();
      const commits = Object.values(p.commits).reduce((a, b) => a + b, 0);
      const own = p.owner.toLowerCase() === data.user.toLowerCase();
      const merged = p.prs.some((x) => x.state === "MERGED");
      const bits: string[] = [];
      if (p.lang) bits.push(p.lang);
      if (commits) bits.push(`${commits} commit${commits > 1 ? "s" : ""}`);
      if (p.prs.length) {
        bits.push(own ? `${p.prs.length} PR${p.prs.length > 1 ? "s" : ""}`
          : merged ? "PR merged" : `PR ${p.prs[0].state.toLowerCase()}`);
      }
      if (!own && p.stars) bits.push(`${num(p.stars)} stars`);
      if (p.fork && p.upstream) bits.push(`fork of ${p.upstream}`);
      return {
        p,
        first: dates[0],
        last: dates[dates.length - 1],
        title: own ? p.name : `${p.owner}/${p.name}`,
        meta: bits.join(" · "),
        note: notes[p.name] ?? "",
        color: LANG[p.lang ?? ""] ?? C.muted,
        weight: commits + p.prs.length,
      };
    })
    .filter((l) => l.first)
    .sort((a, b) => (a.first < b.first ? -1 : 1));

  const by = new Map<string, number>();
  for (const l of lanes) if (l.p.lang) by.set(l.p.lang, (by.get(l.p.lang) ?? 0) + l.weight);
  const lens = [...by.entries()].sort((a, b) => b[1] - a[1]).map(([l]) => l).slice(0, 2).join(" / ") || "-";

  return { longest, peak, active, denseStart: Math.max(0, bestAt), lanes, lens };
}

type Frame = { X0: number; X1: number; FT: number; FB: number; BASE: number; MAXH: number };

function timeline(data: Data, g: Frame) {
  const n = data.days.length;
  const xAt = (i: number) => g.X0 + 6 + (i / (n - 1)) * (g.X1 - g.X0 - 12);
  const xDate = (d: string) => xAt(Math.min(n - 1, Math.max(0, dayIndex(data.from, d))));
  const tAt = (x: number) => DELAY + ((x - g.X0) / (g.X1 - g.X0)) * SWEEP;
  const beamH = (c: number) => Math.min(g.MAXH, 6 + 13 * Math.log2(1 + c));
  return { xAt, xDate, tAt, beamH };
}

function defs(data: Data, g: Frame, fonts: Fonts) {
  const { xAt, beamH } = timeline(data, g);
  const beams: string[] = [];
  data.days.forEach((d, i) => {
    if (!d.count) return;
    const x = xAt(i);
    const w = Math.min(2.2, 0.9 + 0.2 * Math.log2(1 + d.count));
    beams.push(`M${f(x - w / 2)} ${g.BASE}h${f(w)}v${f(-beamH(d.count))}h${f(-w)}z`);
  });
  return `<defs>
<style>
@font-face{font-family:J;font-weight:400;src:url(data:font/woff2;base64,${fonts.regular}) format("woff2")}
@font-face{font-family:J;font-weight:700;src:url(data:font/woff2;base64,${fonts.bold}) format("woff2")}
text{font-family:J,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.slit{transform-box:fill-box;transform-origin:0 0;animation:open ${SWEEP}s linear ${DELAY}s both}
.scan{opacity:0;animation:scan ${SWEEP}s linear ${DELAY}s both}
.lane{animation:develop 1.1s ease-out both}
.exif{animation:develop .8s ease-out both}
.breathe{animation:breathe 7s ease-in-out ${DELAY + SWEEP}s infinite}
.drift{animation:drift 9s ease-in-out ${DELAY + SWEEP}s infinite}
.pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-out infinite}
@keyframes open{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes scan{0%{transform:translateX(0);opacity:1}97%{opacity:1}100%{transform:translateX(${g.X1 - g.X0}px);opacity:0}}
@keyframes develop{from{opacity:0;filter:blur(3px)}to{opacity:1;filter:blur(0)}}
@keyframes breathe{0%,100%{opacity:1}50%{opacity:.82}}
@keyframes drift{0%,100%{transform:translateX(0)}50%{transform:translateX(-5px)}}
@keyframes pulse{0%{transform:scale(.6);opacity:.9}100%{transform:scale(2.6);opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
a{cursor:pointer}
.halo{paint-order:stroke;stroke:${C.film};stroke-width:4px;stroke-linejoin:round}
</style>
<linearGradient id="beam" x1="0" y1="${g.BASE}" x2="0" y2="${g.BASE - g.MAXH}" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="${C.core}"/><stop offset=".35" stop-color="${C.warm}"/><stop offset="1" stop-color="${C.ember}" stop-opacity=".15"/>
</linearGradient>
<linearGradient id="slitg" x1="0" x2="1"><stop offset="0" stop-color="${C.core}" stop-opacity="0"/><stop offset="1" stop-color="${C.core}" stop-opacity=".55"/></linearGradient>
<radialGradient id="vig" cx=".5" cy=".45" r=".75"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>
<filter id="smear" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="14 2.5"/></filter>
<filter id="bloom" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="5 3"/></filter>
<filter id="glow" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="1.2 .4"/></filter>
<filter id="grain" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="7" stitchTiles="stitch"/>
<feColorMatrix values="0 0 0 0 1  0 0 0 0 .85  0 0 0 0 .6  0 0 0 .5 0"/>
</filter>
<clipPath id="exposed"><rect class="slit" x="${g.X0}" y="${g.FT}" width="${g.X1 - g.X0}" height="${g.FB - g.FT}"/></clipPath>
<path id="beams" d="${beams.join("")}"/>
</defs>`;
}

// Film, light, slit and the "now" marker. `inside` is drawn within the
// exposed clip (annotations that should develop with the light).
function film(data: Data, g: Frame, inside: string) {
  const { xAt } = timeline(data, g);
  const dust = data.days.map((d, i) => (d.count ? "" : `M${f(xAt(i))} ${g.BASE}h.9`)).join("");
  return `<rect x="${g.X0}" y="${g.FT}" width="${g.X1 - g.X0}" height="${g.FB - g.FT}" rx="3" fill="${C.film}" stroke="${C.rule}"/>
<path d="${dust}" stroke="${C.dim}" stroke-width="1"/>
<g clip-path="url(#exposed)">
<g class="breathe">
<g class="drift">
<use href="#beams" fill="${C.ember}" filter="url(#smear)" opacity=".55" transform="translate(-22 0)"/>
<use href="#beams" fill="${C.warm}" filter="url(#smear)" opacity=".5" transform="translate(-10 0)"/>
</g>
<use href="#beams" fill="url(#beam)" filter="url(#bloom)" opacity=".9"/>
<use href="#beams" fill="url(#beam)" filter="url(#glow)"/>
<use href="#beams" fill="${C.core}" opacity=".55"/>
<use href="#beams" fill="${C.warm}" filter="url(#smear)" opacity=".12" transform="matrix(1 0 0 -.32 0 ${f(g.BASE * 1.32)})"/>
</g>
${inside}
</g>
<line x1="${g.X0 + 6}" y1="${g.BASE + 0.5}" x2="${g.X1 - 6}" y2="${g.BASE + 0.5}" stroke="${C.rule}"/>`;
}

function filmTop(g: Frame) {
  return `<rect class="scan" x="${g.X0 - 18}" y="${g.FT + 1}" width="20" height="${g.FB - g.FT - 2}" fill="url(#slitg)"/>
<line x1="${g.X1 - 6}" y1="${g.FT + 8}" x2="${g.X1 - 6}" y2="${g.FB - 8}" stroke="${C.accent}" stroke-opacity=".35" stroke-dasharray="2 3"/>
<circle class="pulse" cx="${g.X1 - 6}" cy="${g.BASE}" r="4" fill="none" stroke="${C.accent}"/>
<circle cx="${g.X1 - 6}" cy="${g.BASE}" r="2" fill="${C.accent}"/>
<text x="${g.X1 - 10}" y="${g.FT + 14}" fill="${C.accent}" font-size="9" text-anchor="end" opacity=".8">now</text>
<rect x="${g.X0}" y="${g.FT}" width="${g.X1 - g.X0}" height="${g.FB - g.FT}" rx="3" fill="url(#vig)" pointer-events="none"/>
<rect x="${g.X0}" y="${g.FT}" width="${g.X1 - g.X0}" height="${g.FB - g.FT}" filter="url(#grain)" opacity=".07" pointer-events="none"/>`;
}

function marks(data: Data, g: Frame, l: Lane, y: number) {
  const { xDate } = timeline(data, g);
  const xa = xDate(l.first), xb = Math.max(xDate(l.last), xa + 2);
  const ticks = Object.entries(l.p.commits).map(([d, c]) =>
    `<circle cx="${f(xDate(d))}" cy="${f(y)}" r="${f(Math.min(4.6, 1.5 + 0.9 * Math.sqrt(c)))}"/>`).join("");
  const prs = l.p.prs.map((x) =>
    `<circle cx="${f(xDate(x.date))}" cy="${f(y)}" r="3.6" fill="${C.film}" stroke="${l.color}" stroke-width="1.1"/>`).join("");
  return `<line x1="${f(xa)}" y1="${f(y)}" x2="${f(xb)}" y2="${f(y)}" stroke="${l.color}" stroke-width="1.4" opacity=".45"/>
<g fill="${l.color}">${ticks}</g>${prs}`;
}

function months(data: Data, g: Frame, y: number, tick: boolean) {
  const { xAt } = timeline(data, g);
  return data.days.map((d, i) => {
    if (!d.date.endsWith("-01")) return "";
    const x = xAt(i);
    return (tick ? `<path d="M${f(x)} ${g.FB - 5}v5" stroke="${C.dim}"/>` : "") +
      `<text x="${f(x + 2)}" y="${y}" fill="${C.quiet}" font-size="${tick ? 9 : 8}" letter-spacing="${tick ? 1 : 0.4}">${MONTHS[+d.date.slice(5, 7) - 1]}</text>`;
  }).join("");
}

function exifItems(data: Data, m: ReturnType<typeof model>): [string, string][] {
  return [
    ["CONTRIBUTIONS", big(data.totals.contributions)],
    ["PRIVATE", big(data.totals.private)],
    ["PUBLIC COMMITS", big(data.totals.commits)],
    ["PULL REQUESTS", big(data.totals.prs)],
    ["ACTIVE DAYS", big(m.active)],
    ["LONGEST RUN", `${m.longest}<tspan font-size="12" fill="${C.quiet}" dx="2">d</tspan>`],
    ["STARS", big(data.totals.stars)],
  ];
}

function exifCell(x: number, y: number, k: string, v: string, i: number, spacing = 1.2) {
  return `<g class="exif" style="animation-delay:${f(DELAY + SWEEP + 0.1 + i * 0.07)}s">` +
    `<text x="${f(x)}" y="${y}" fill="${C.paper}" font-size="23" font-weight="700">${v}</text>` +
    `<text x="${f(x)}" y="${y + 18}" fill="${C.quiet}" font-size="8.5" letter-spacing="${spacing}">${k}</text></g>`;
}

function shell(data: Data, W: number, H: number, m: ReturnType<typeof model>, body: string) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-labelledby="t d">
<title id="t">${esc(data.user)}: one year as a single exposure</title>
<desc id="d">${esc(`${num(data.totals.contributions)} contributions from ${data.from} to ${data.to}, ${num(data.totals.private)} of them private. Public projects: ${m.lanes.map((l) => l.p.name).join(", ")}.`)}</desc>
${body}
</svg>`;
}

function wide(data: Data, fonts: Fonts, m: ReturnType<typeof model>) {
  const g: Frame = { X0: 36, X1: 764, FT: 100, FB: 358, BASE: 214, MAXH: 92 };
  const EX = g.FB + 26;
  const W = 800, H = EX + 104;
  const { xAt, xDate, tAt, beamH } = timeline(data, g);

  const px = xAt(data.days.indexOf(m.peak)), ph = beamH(m.peak.count);
  const dense = xAt(m.denseStart);
  const inside = `<path d="M${f(px)} ${f(g.BASE - ph - 3)}v-6" stroke="${C.muted}"/>
<text class="halo" x="${f(px)}" y="${f(g.BASE - ph - 12)}" fill="${C.muted}" font-size="9" text-anchor="${px > g.X1 - 90 ? "end" : "middle"}">peak ${m.peak.count} · ${human(m.peak.date).slice(0, -5)}</text>
<text class="halo" x="${f(dense - 16)}" y="${g.FT + 42}" fill="${C.paper}" font-size="11.5" font-weight="700" text-anchor="end">${num(data.totals.private)} private contributions</text>
<text class="halo" x="${f(dense - 16)}" y="${g.FT + 57}" fill="${C.quiet}" font-size="9.5" text-anchor="end">names withheld, light kept</text>
<path d="M${f(dense - 10)} ${g.FT + 38}h8v18" fill="none" stroke="${C.quiet}"/>`;

  const LANE0 = 244, LANE_H = Math.min(21, (g.FB - 14 - LANE0) / Math.max(1, m.lanes.length - 1));
  const lanes = m.lanes.map((l, k) => {
    const y = LANE0 + k * LANE_H;
    const xa = xDate(l.first), xb = Math.max(xDate(l.last), xa + 2);
    const labelW = textW(l.title, 12) + 10 + textW(l.meta, 10.5) + (l.note ? 10 + textW(l.note, 10.5) + 12 : 0);
    const right = xb + 10 + labelW < g.X1 - 18;
    // tspans keep reading order intact when the label flips to end-anchor
    const parts = `<tspan fill="${C.paper}" font-weight="700" font-size="12">${esc(l.title)}</tspan>` +
      `<tspan dx="10" fill="${C.quiet}">${esc(l.meta)}</tspan>` +
      (l.note ? `<tspan dx="10" fill="${C.accent}" font-weight="700">${esc(l.note)}</tspan>` : "");
    return `<a href="${esc(l.p.url)}" target="_blank"><g class="lane" style="animation-delay:${f(tAt(xa))}s">
${marks(data, g, l, y)}
<text x="${f(right ? xb + 10 : xa - 10)}" y="${f(y + 4)}" font-size="10.5" text-anchor="${right ? "start" : "end"}">${parts}</text>
</g></a>`;
  }).join("\n");

  const items = exifItems(data, m);
  const colW = (g.X1 - g.X0) / items.length;
  const footer = [`CAMERA ${data.user.toUpperCase()}`, `LENS ${m.lens.toUpperCase()}`, `SHUTTER 365 d`, `DEVELOPED ${human(data.to)}`];

  return shell(data, W, H, m, `${defs(data, g, fonts)}
<rect width="${W}" height="${H}" fill="${C.bg}"/>
<text x="${g.X0}" y="58" fill="${C.paper}" font-size="34" font-weight="700" letter-spacing="-.5">${esc(data.user)}</text>
<text x="${g.X0}" y="80" fill="${C.quiet}" font-size="10.5">one year, one frame. every working day leaves light, <tspan fill="${C.muted}">public work comes out sharp</tspan>.</text>
<text x="${g.X1}" y="44" fill="${C.muted}" font-size="10" letter-spacing="2" text-anchor="end">EXPOSURE · 365 DAYS</text>
<text x="${g.X1}" y="62" fill="${C.quiet}" font-size="10" text-anchor="end">${human(data.from)} → ${human(data.to)}</text>
<g fill="${C.quiet}" font-size="9">
<circle cx="${g.X1 - 92}" cy="77" r="2.6" fill="${C.muted}"/><text x="${g.X1 - 86}" y="80">commit</text>
<circle cx="${g.X1 - 20}" cy="77" r="3" fill="none" stroke="${C.muted}"/><text x="${g.X1}" y="80" text-anchor="end">PR</text></g>
${film(data, g, inside)}
${lanes}
${filmTop(g)}
${months(data, g, g.FB + 14, true)}
<line x1="${g.X0}" y1="${EX}" x2="${g.X1}" y2="${EX}" stroke="${C.rule}"/>
${items.map(([k, v], i) => exifCell(g.X0 + i * colW, EX + 32, k, v, i)).join("\n")}
<line x1="${g.X0}" y1="${EX + 66}" x2="${g.X1}" y2="${EX + 66}" stroke="${C.rule}"/>
<text y="${EX + 86}" fill="${C.quiet}" font-size="8.5" letter-spacing="1.2">${footer
    .map((t, i) => `<tspan x="${f(g.X0 + i * colW * 1.75)}">${esc(t)}</tspan>`).join("")}</text>`);
}

// Phone frame: same light, but projects are stacked rows (name, meta, own
// timeline track) because inline labels would not fit at 360px.
function tall(data: Data, fonts: Fonts, m: ReturnType<typeof model>) {
  const ROW = 50;
  const g0 = { X0: 16, X1: 384, FT: 118, BASE: 240, MAXH: 100 };
  const LANE0 = g0.BASE + 52;
  const g: Frame = { ...g0, FB: LANE0 + m.lanes.length * ROW - 8 };
  const EX = g.FB + 22;
  const W = 400;
  const { xAt, xDate, tAt } = timeline(data, g);

  const dense = xAt(m.denseStart);
  const inside = `<text class="halo" x="${f(dense - 12)}" y="${g.FT + 22}" fill="${C.paper}" font-size="11.5" font-weight="700" text-anchor="end">${num(data.totals.private)} private</text>
<text class="halo" x="${f(dense - 12)}" y="${g.FT + 36}" fill="${C.quiet}" font-size="9.5" text-anchor="end">names withheld, light kept</text>`;

  const lanes = m.lanes.map((l, k) => {
    const y = LANE0 + k * ROW;
    const xa = xDate(l.first);
    return `<a href="${esc(l.p.url)}" target="_blank"><g class="lane" style="animation-delay:${f(tAt(xa))}s">
<text x="${g.X0 + 10}" y="${y}" font-size="12.5" font-weight="700" fill="${C.paper}">${esc(l.title)}${l.note ? `<tspan dx="8" font-size="10.5" fill="${C.accent}">${esc(l.note)}</tspan>` : ""}</text>
<text x="${g.X0 + 10}" y="${y + 15}" font-size="10" fill="${C.quiet}">${esc(l.meta)}</text>
<line x1="${g.X0 + 6}" y1="${y + 28}" x2="${g.X1 - 6}" y2="${y + 28}" stroke="${C.dim}" stroke-dasharray="1 3"/>
${marks(data, g, l, y + 28)}
</g></a>`;
  }).join("\n");

  const items = exifItems(data, m);
  const cols = 4, colW = (g.X1 - g.X0) / cols, rowH = 54;
  const rows = Math.ceil(items.length / cols);
  const FOOT = EX + rows * rowH + 14;
  const H = FOOT + 46;

  return shell(data, W, H, m, `${defs(data, g, fonts)}
<rect width="${W}" height="${H}" fill="${C.bg}"/>
<text x="${g.X0}" y="30" fill="${C.muted}" font-size="9" letter-spacing="2">EXPOSURE · 365 DAYS</text>
<text x="${g.X0}" y="64" fill="${C.paper}" font-size="32" font-weight="700" letter-spacing="-.5">${esc(data.user)}</text>
<text x="${g.X0}" y="84" fill="${C.quiet}" font-size="10">${human(data.from)} → ${human(data.to)}</text>
<text x="${g.X0}" y="102" fill="${C.quiet}" font-size="10">every working day leaves light, <tspan fill="${C.muted}">public work is sharp</tspan>.</text>
${film(data, g, inside)}
${months(data, g, g.BASE + 18, false)}
<line x1="${g.X0 + 10}" y1="${g.BASE + 30}" x2="${g.X1 - 10}" y2="${g.BASE + 30}" stroke="${C.rule}" stroke-dasharray="1 3"/>
${lanes}
${filmTop(g)}
<line x1="${g.X0}" y1="${EX}" x2="${g.X1}" y2="${EX}" stroke="${C.rule}"/>
${items.map(([k, v], i) => exifCell(g.X0 + (i % cols) * colW, EX + 32 + Math.floor(i / cols) * rowH, k, v, i, 0.4)).join("\n")}
<line x1="${g.X0}" y1="${FOOT}" x2="${g.X1}" y2="${FOOT}" stroke="${C.rule}"/>
<text x="${g.X0}" y="${FOOT + 20}" fill="${C.quiet}" font-size="8.5" letter-spacing="1.2">CAMERA ${esc(data.user.toUpperCase())} · LENS ${esc(m.lens.toUpperCase())}</text>
<text x="${g.X0}" y="${FOOT + 34}" fill="${C.quiet}" font-size="8.5" letter-spacing="1.2">SHUTTER 365 d · DEVELOPED ${human(data.to)}</text>`);
}

export function render(data: Data, fonts: Fonts, notes: Notes = {}, layout: Layout = "wide") {
  const m = model(data, notes);
  return layout === "wide" ? wide(data, fonts, m) : tall(data, fonts, m);
}
