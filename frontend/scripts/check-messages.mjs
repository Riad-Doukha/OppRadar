// Fails when fr/ar message files miss keys that en has (or have extra ones),
// or when a translation drops an ICU {placeholder} the English text uses.
import fs from "node:fs";
import path from "node:path";

const dir = path.resolve(import.meta.dirname, "..", "messages");
const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) => (v && typeof v === "object" ? flat(v, `${p}${k}.`) : [[`${p}${k}`, String(v)]]));
// "{name}" or "{name, plural …}" — not the words inside a branch like "=0 {closes today}".
const args = (s) => new Set([...s.matchAll(/\{(\w+)\s*[,}]/g)].map((m) => m[1]));
let problems = 0;
for (const file of fs.readdirSync(path.join(dir, "en"))) {
  const en = new Map(flat(JSON.parse(fs.readFileSync(path.join(dir, "en", file), "utf8"))));
  for (const loc of ["fr", "ar"]) {
    const p = path.join(dir, loc, file);
    if (!fs.existsSync(p)) { console.log(`${loc}/${file}: missing file`); problems++; continue; }
    const other = new Map(flat(JSON.parse(fs.readFileSync(p, "utf8"))));
    for (const [k, v] of en) {
      if (!other.has(k)) { console.log(`${loc}/${file}: missing ${k}`); problems++; continue; }
      for (const a of args(v)) if (!args(other.get(k)).has(a)) { console.log(`${loc}/${file}: ${k} lacks {${a}}`); problems++; }
    }
    for (const k of other.keys()) if (!en.has(k)) { console.log(`${loc}/${file}: extra ${k}`); problems++; }
  }
}
if (problems) { console.log(`${problems} problem(s)`); process.exit(1); }
console.log("messages: en/fr/ar in sync");
