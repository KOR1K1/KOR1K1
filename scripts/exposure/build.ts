// Usage:
//   GH_TOKEN=... node --experimental-strip-types scripts/exposure/build.ts
//   node --experimental-strip-types scripts/exposure/build.ts --offline   (re-render docs/data.json)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { fetchData, type Data } from "./fetch.ts";
import { render } from "./render.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const at = (p: string) => join(root, p);
const user = process.env.GH_USER ?? "KOR1K1";

let data: Data;
if (process.argv.includes("--offline")) {
  data = JSON.parse(readFileSync(at("docs/data.json"), "utf8"));
} else {
  const token = process.env.GH_TOKEN;
  if (!token) throw new Error("GH_TOKEN is required (or pass --offline)");
  data = await fetchData(user, token);
  mkdirSync(at("docs"), { recursive: true });
  writeFileSync(at("docs/data.json"), JSON.stringify(data, null, 2) + "\n");
}

const font = (w: string) => readFileSync(at(`assets/fonts/jbm-${w}.woff2`)).toString("base64");
const notes = JSON.parse(readFileSync(at("scripts/exposure/notes.json"), "utf8"));
const fonts = { regular: font("Regular"), bold: font("Bold") };
for (const [layout, file] of [["wide", "assets/exposure.svg"], ["tall", "assets/exposure-mobile.svg"]] as const) {
  const svg = render(data, fonts, notes, layout);
  writeFileSync(at(file), svg);
  console.log(`${file} ${(svg.length / 1024).toFixed(1)} KB`);
}
