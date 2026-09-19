// Rasterize a brand SVG into PNG icons for the /waiter PWA manifest.
// Run with `node scripts/gen-waiter-icons.mjs` to (re)generate the default
// SYNORA icons, or `node scripts/gen-waiter-icons.mjs <path-to-logo.svg>` to
// rebrand /waiter for a client deployment (pair with the WAITER_APP_NAME /
// WAITER_APP_SHORT_NAME / WAITER_APP_THEME_COLOR env vars — see .env.example).
import sharp from "sharp";
import { mkdirSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join, resolve } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const svgPath = process.argv[2] ? resolve(process.argv[2]) : join(root, "src/app/icon.svg");
const outDir = join(root, "public/waiter");

console.log(`source logo: ${svgPath}`);

mkdirSync(outDir, { recursive: true });

const sizes = [192, 512];
for (const size of sizes) {
  await sharp(svgPath, { density: 384 })
    .resize(size, size)
    .png()
    .toFile(join(outDir, `icon-${size}.png`));
  console.log(`wrote icon-${size}.png`);
}

// iOS "Add to Home Screen" reads apple-touch-icon, not the web manifest.
await sharp(svgPath, { density: 384 })
  .resize(180, 180)
  .png()
  .toFile(join(outDir, "apple-touch-icon.png"));
console.log("wrote apple-touch-icon.png");
