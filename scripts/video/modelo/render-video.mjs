import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), enableCaching: false });
const ID = process.env.COMP || "Criativo-Story";
const composition = await selectComposition({ serveUrl, id: ID });
await renderMedia({ serveUrl, composition, codec: "h264", crf: 18, concurrency: 4, outputLocation: path.resolve(process.argv[2]) });
console.log("ok");
