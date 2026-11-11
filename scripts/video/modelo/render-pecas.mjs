// Camadas do storyboard editável: por cena, o FUNDO (bruto + cena sem as peças) e cada PEÇA
// sozinha em PNG com alfa, no canvas inteiro. Depois:
//   python -m scripts.video.storyboard pecas <saida>   → corta pelo alfa e grava pecas.json
// uso: node render-pecas.mjs [story|feed|h] [cena1,cena2]
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";

const formato = process.argv[2] || "story";
const so = process.argv[3] ? process.argv[3].split(",") : null;
const ID = { story: "Criativo-Story", feed: "Criativo-Feed", h: "Criativo-Horizontal" }[formato];
const criativo = JSON.parse(fs.readFileSync("src/data/criativo.resolvido.json", "utf-8"));

// peças de cada cena, na ordem de empilhamento; "mãe>filha" = filha dentro da mãe (frame no Figma).
// Tem que bater com os <Peca id> de src/cenas/*.tsx (peça que não aparece sai vazia e é pulada).
const NA_FOLHA = (...ids) => ["folha", ...ids.map((i) => `folha>${i}`)];
const PECAS = {
  Desenho: (p) => ["imagem", ...p.etiquetas.map((_, i) => `etiquetas[${i}]`)],
  Manchete: () => NA_FOLHA("kicker", "titulo", "corpo"),
  Grafico: () => ["kicker", "numero", "grafico", "rotuloFim", "selo"],
  Carimbo: () => NA_FOLHA("kicker", "pergunta", "carimbo", "corpo", "mao"),
  Rota: () => ["kicker", "titulo", "selo", "rotuloCume"],
  PapelMesa: () => [...NA_FOLHA("kicker", "titulo", "grafico", "mao"), "adesivo"],
  Cartao: () => ["cartao", "cartao>kicker", "cartao>titulo", "cartao>subtitulo", "cartao>carimbo"],
  Checklist: (p) => ["kicker", "titulo", ...p.itens.map((_, i) => `itens[${i}]`)],
  Contador: () => ["kicker", "numero", "medalhas"],
  Splash: () => ["faixa", "imagem", "titulo", "subtitulo"],
  Cta: () => ["botao", "chamada"],
};

// instante do storyboard: 0,4 s antes do fim. Exceção: o título da Rota sai de cena antes
// (em.saiTitulo), então kicker/título são fotografados logo antes de sumir.
const instante = (c, id) =>
  c.componente === "Rota" && ["kicker", "titulo"].includes(id) && c.props.em?.saiTitulo
    ? c.props.em.saiTitulo - 0.2
    : c.ate - 0.4;

const saida = path.resolve(`../output/pecas/${criativo.codigo}/${formato}`);
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), enableCaching: false });
for (const c of criativo.cenas) {
  if (so && !so.includes(c.id)) continue;
  const pasta = path.join(saida, c.id);
  fs.mkdirSync(pasta, { recursive: true });
  const lista = PECAS[c.componente](c.props).map((s) => {
    const [pai, id] = s.includes(">") ? s.split(">") : [null, s];
    return pai ? { id, pai } : { id };
  });
  const still = async (isolar, id, arquivo) => {
    const inputProps = { formato, soCena: c.id, isolar };
    const composition = await selectComposition({ serveUrl, id: ID, inputProps });
    await renderStill({ serveUrl, composition, inputProps, frame: Math.round(instante(c, id) * 30),
      output: path.join(pasta, arquivo), imageFormat: "png" });
  };
  await still("__fundo__", null, "fundo.png");
  for (const p of lista) {
    await still(p.id, p.id, `${p.id}.png`);
    await still(`caixa:${p.id}`, p.id, `${p.id}.caixa.png`); // centro = origem de giro/escala
  }
  await still("__legenda__", null, "legenda.png");
  fs.writeFileSync(path.join(pasta, "lista.json"), JSON.stringify(lista));
  console.log("ok", c.id, lista.length, "peças");
}
