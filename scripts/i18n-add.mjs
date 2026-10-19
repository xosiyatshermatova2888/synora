// Insert keys into a namespace of all three locale files WITHOUT reformatting
// the rest of the file (the files mix inline and expanded objects, CRLF/LF).
// Usage: node scripts/i18n-add.mjs spec.json
// spec: { "path": "shell.overview", "uz": {k: v}, "ru": {...}, "en": {...} }
// Existing keys in the target object are never overwritten (throws instead),
// because a silent duplicate key is how translations get lost.
import fs from "node:fs";

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const target = spec.path ? spec.path.split(".") : [];

function locate(raw) {
  if (target.length === 0) return { open: raw.indexOf("{"), close: raw.lastIndexOf("}") };
  const stack = [];
  let i = 0;
  let found = null;
  while (i < raw.length) {
    const ch = raw[i];
    if (ch === '"') {
      let j = i + 1;
      while (raw[j] !== '"') j += raw[j] === "\\" ? 2 : 1;
      const str = raw.slice(i + 1, j);
      let k = j + 1;
      while (/\s/.test(raw[k])) k++;
      if (raw[k] === ":") {
        let m = k + 1;
        while (/\s/.test(raw[m])) m++;
        if (raw[m] === "{") {
          stack.push({ key: str, open: m });
          const path = stack.map((s) => s.key).filter(Boolean);
          if (path.length === target.length && path.every((p, idx) => p === target[idx])) {
            found = { open: m };
          }
          i = m + 1;
          continue;
        }
      }
      i = j + 1;
      continue;
    }
    if (ch === "{") stack.push({ key: null, open: i });
    else if (ch === "}") {
      const frame = stack.pop();
      if (found && frame.open === found.open && found.close === undefined) found.close = i;
    }
    i++;
  }
  if (!found || found.close === undefined) throw new Error(`namespace not found: ${spec.path}`);
  return found;
}

for (const loc of ["uz", "ru", "en"]) {
  const file = `src/messages/${loc}.json`;
  let raw = fs.readFileSync(file, "utf8");
  const nl = raw.includes("\r\n") ? "\r\n" : "\n";

  let node = JSON.parse(raw);
  for (const seg of target) node = node?.[seg];
  if (!node) throw new Error(`[${loc}] namespace missing: ${spec.path}`);
  const entries = Object.entries(spec[loc] ?? {});
  for (const [k] of entries) {
    if (k in node) throw new Error(`[${loc}] key already exists: ${spec.path}.${k}`);
  }
  if (!entries.length) continue;

  const { close } = locate(raw);
  let lastNonWs = close - 1;
  while (/\s/.test(raw[lastNonWs])) lastNonWs--;
  let lineStart = close;
  while (lineStart > 0 && raw[lineStart - 1] !== "\n") lineStart--;
  const closeIndent = raw.slice(lineStart, close).match(/^\s*/)[0];
  const indent = closeIndent + "  ";
  const body = entries
    .map(([k, v]) => `${indent}${JSON.stringify(k)}: ${JSON.stringify(v, null, 2).replace(/\n/g, nl + indent)}`)
    .join("," + nl);
  raw = raw.slice(0, lastNonWs + 1) + "," + nl + body + raw.slice(lastNonWs + 1);
  JSON.parse(raw);
  fs.writeFileSync(file, raw);
}
console.log(`added to ${spec.path}`);
