// Storyboard de vídeo animado no Figma (script para o use_figma do Figma MCP).
//
// Antes de colar no use_figma, troque:
//   __PAGINA__ → id da página "<COD> — Storyboard" (ex.: "1:3")
//   __DADOS__  → conteúdo de `python -m scripts.video.storyboard ... --saida out/storyboard.json`
// Depois suba o quadro renderizado de cada cena (render-stills, 0,4 s antes do fim) com
// upload_assets nos nodeIds `imagens` que este script devolve, na ordem das telas.
//
// Cada tela: cabeçalho (id · componente · de→até), imagem 540×960, Status, fala, efeitos
// e os TEXTOS EDITÁVEIS — uma camada TEXT por prop, com o caminho da prop no nome
// ("destaque.texto"). O usuário edita esses textos e troca o Status para "Aprovado";
// o Claude lê de volta só as telas aprovadas (scripts/video/storyboard.py:
// diferencas_textos → lista para o usuário → aplicar_textos).
const PAGINA = "__PAGINA__";
const DADOS = __DADOS__;

const page = await figma.getNodeByIdAsync(PAGINA);
await figma.setCurrentPageAsync(page);
await figma.loadFontAsync({ family: "Inter", style: "Regular" });
await figma.loadFontAsync({ family: "Inter", style: "Bold" });

function texto(t, size, bold, nome, cor) {
  const n = figma.createText();
  n.fontName = { family: "Inter", style: bold ? "Bold" : "Regular" };
  n.characters = t;
  n.fontSize = size;
  if (nome) n.name = nome;
  if (cor) n.fills = [{ type: "SOLID", color: cor }];
  return n;
}
const CINZA = { r: 0.45, g: 0.45, b: 0.45 };

// idempotente: refaz só as telas deste criativo (nomes "Tela · <id>")
page.findChildren((n) => n.name.startsWith("Tela · ")).forEach((n) => n.remove());

const telas = [];
const imagens = [];
DADOS.telas.forEach((t, i) => {
  const col = figma.createAutoLayout("VERTICAL", { name: `Tela · ${t.id}`, itemSpacing: 16 });
  col.x = i * 620;
  col.y = 0;
  page.appendChild(col);
  col.appendChild(texto(`${i + 1}. ${t.id} · ${t.componente} · ${t.de}s → ${t.ate}s`, 24, true, "cabeçalho"));
  const img = figma.createFrame();
  img.name = "imagem";
  img.resize(540, 960);
  img.fills = [{ type: "SOLID", color: { r: 0.15, g: 0.15, b: 0.15 } }];
  col.appendChild(img);
  imagens.push(img.id);
  col.appendChild(texto("Status: Proposta", 22, true, "status", { r: 0.91, g: 0.39, b: 0.24 }));
  const blocos = [["Fala", t.fala], ["Efeitos", t.efeitos.join(" · ") || "—"]];
  for (const [rot, val] of blocos) {
    col.appendChild(texto(rot.toUpperCase(), 14, true, `rótulo ${rot}`, CINZA));
    const v = texto(val, 18, false, rot.toLowerCase());
    v.textAutoResize = "HEIGHT";
    v.resize(540, v.height);
    col.appendChild(v);
  }
  col.appendChild(texto("TEXTOS EDITÁVEIS (o nome da camada é o campo — não renomeie)", 14, true, "rótulo textos", CINZA));
  const grupo = figma.createAutoLayout("VERTICAL", { name: "textos", itemSpacing: 10 });
  col.appendChild(grupo);
  for (const [caminho, valor] of Object.entries(t.textos)) {
    grupo.appendChild(texto(caminho, 12, false, `rótulo ${caminho}`, CINZA));
    const v = texto(valor, 20, true, caminho);
    v.textAutoResize = "HEIGHT";
    v.resize(540, v.height);
    grupo.appendChild(v);
  }
  telas.push(col.id);
});
return { telas, imagens, total: telas.length };
