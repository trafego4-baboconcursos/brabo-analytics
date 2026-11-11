// Prévia leve: renderiza só um trecho, em meia resolução, com áudio.
// uso: node render-clip.mjs <de_seg> <ate_seg> <nome>
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";

const [de, ate, nome] = process.argv.slice(2);
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), enableCaching: false });
const ID = process.env.COMP || "Criativo-Story";
const composition = await selectComposition({ serveUrl, id: ID });
const out = path.resolve(`../output/previa/${nome}.mp4`);
await renderMedia({
  serveUrl,
  composition,
  codec: "h264",
  crf: 26,
  scale: 0.5,
  concurrency: 4,
  frameRange: [Math.round(Number(de) * 30), Math.round(Number(ate) * 30) - 1],
  outputLocation: out,
});
console.log("ok", out);
