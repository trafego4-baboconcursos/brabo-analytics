import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
// uso: node render-stills.mjs [--scale=1] seg1 seg2 ...
const args = process.argv.slice(2);
const scale = Number((args.find((a) => a.startsWith("--scale=")) || "--scale=0.4").split("=")[1]);
const secs = args.filter((a) => !a.startsWith("--")).map(Number);
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), enableCaching: false });
const ID = process.env.COMP || "AD358-Referencia";
const composition = await selectComposition({ serveUrl, id: ID });
for (const s of secs) {
  const out = path.resolve(`../output/frames/${ID === "AD358-Referencia" ? "" : ID + "_"}f_${String(s).replace(".", "_")}${scale === 1 ? "_full" : ""}.jpg`);
  await renderStill({ serveUrl, composition, frame: Math.round(s * 30), output: out, imageFormat: "jpeg", jpegQuality: 92, scale });
  console.log("ok", s);
}
