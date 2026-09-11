// One-off script: rasterize the existing brand SVG (src/app/icon.svg) into
// PNG icons for the /waiter PWA manifest. Run with `node scripts/gen-waiter-icons.mjs`.
import sharp from "sharp";
import { mkdirSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const svgPath = join(root, "src/app/icon.svg");
const outDir = join(root, "public/waiter");

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
