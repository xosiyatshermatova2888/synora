// Detects duplicate keys inside the same JSON object (JSON.parse silently keeps
// the last one) and key-set drift between the three locale files.
// Usage: node scripts/check-i18n.mjs
import fs from "node:fs";

const LOCALES = ["uz", "ru", "en"];

function duplicates(raw) {
  const dupes = [];
  const stack = [];
  const path = [];
  const token = /"((?:[^"\\]|\\.)*)"(\s*:)?|[{}[\]]/g;
  let m;
  while ((m = token.exec(raw))) {
    const t = m[0];
    if (t === "{") stack.push(new Set());
    else if (t === "}") stack.pop();
    else if (m[2] && stack.length) {
      const seen = stack[stack.length - 1];
      if (seen.has(m[1])) dupes.push(`${path.join(".")}.${m[1]}`);
      seen.add(m[1]);
    }
  }
  return dupes;
}

function flatten(obj, prefix = "", out = new Set()) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object") flatten(v, key, out);
    else out.add(key);
  }
  return out;
}

let failed = false;
const keySets = {};
for (const l of LOCALES) {
  const raw = fs.readFileSync(`src/messages/${l}.json`, "utf8");
  const d = duplicates(raw);
  if (d.length) {
    failed = true;
    console.log(`[${l}] duplicate keys:`, d);
  }
  keySets[l] = flatten(JSON.parse(raw));
}
for (const l of LOCALES.slice(1)) {
  const missing = [...keySets.uz].filter((k) => !keySets[l].has(k));
  const extra = [...keySets[l]].filter((k) => !keySets.uz.has(k));
  if (missing.length || extra.length) {
    failed = true;
    console.log(`[${l}] missing vs uz:`, missing.slice(0, 20), "extra:", extra.slice(0, 20));
  }
}
console.log(failed ? "i18n check FAILED" : "i18n check OK");
process.exit(failed ? 1 : 0);
