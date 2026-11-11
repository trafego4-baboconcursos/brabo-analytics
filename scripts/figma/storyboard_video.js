// Storyboard de vídeo animado no Figma (script para o use_figma do Figma MCP).
//
// Antes de colar no use_figma, troque:
//   __PAGINA__ → id da página "<COD> — Storyboard" (ex.: "1:3")
//   __DADOS__  → conteúdo de `python -m scripts.video.storyboard <resolvido> --captions … --saida out/storyboard.json
//                [--camadas <output>/pecas/<COD>/story]`
// Depois suba as imagens com upload_assets (nodeIds = `uploads[].no`, na ordem; no máx. 60 por chamada)
// e POST de cada `uploads[].arquivo` (relativo à pasta das camadas) na URL devolvida.
//
// Cada tela: cabeçalho, PALCO 540×960 (metade do vídeo 1080×1920), Status, fala, efeitos e textos.
// - Tela com camadas: no palco, "fundo" (travado), uma camada por PEÇA com o nome do id
//   ("titulo", "etiquetas[0]") e "legenda" (travada, por cima). Peça filha (kicker da folha) fica
//   DENTRO do frame da mãe. O usuário arrasta, gira e redimensiona as peças; o Claude lê de volta
//   com storyboard_ler_camadas.js → storyboard.py (diferencas_ajustes → lista → aplicar_ajustes).
// - Tela sem camadas: o palco recebe o still da cena (render-stills, 0,4 s antes do fim).
// Textos: uma camada TEXT por prop, com o caminho da prop no nome ("destaque.texto"); volta por
// diferencas_textos → aplicar_textos. O Status de cada tela é mantido ao refazer a página.
const PAGINA = "__PAGINA__";
const DADOS = __DADOS__;
const K = 0.5; // palco = vídeo × 0,5

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
function quadro(nome, x, y, w, h, pai) {
  const f = figma.createFrame();
  f.name = nome;
  f.resize(Math.max(1, w), Math.max(1, h));
  f.x = x;
  f.y = y;
  f.fills = [];
  f.clipsContent = false;
  pai.appendChild(f);
  return f;
}
const CINZA = { r: 0.45, g: 0.45, b: 0.45 };

// idempotente: refaz só as telas deste criativo (nomes "Tela · <id>"), guardando o Status
const statusAntes = {};
for (const n of page.findChildren((n) => n.name.startsWith("Tela · "))) {
  const st = n.findOne((c) => c.name === "status" && c.type === "TEXT");
  if (st) statusAntes[n.name.slice(7)] = st.characters;
  n.remove();
}

const telas = [];
const uploads = []; // { no, arquivo } — arquivo null = still da cena (tela sem camadas)
DADOS.telas.forEach((t, i) => {
  const col = figma.createAutoLayout("VERTICAL", { name: `Tela · ${t.id}`, itemSpacing: 16 });
  col.x = i * 620;
  col.y = 0;
  page.appendChild(col);
  col.appendChild(texto(`${i + 1}. ${t.id} · ${t.componente} · ${t.de}s → ${t.ate}s`, 24, true, "cabeçalho"));
  const palco = figma.createFrame();
  palco.name = "palco";
  palco.resize(540, 960);
  palco.clipsContent = true;
  palco.fills = [{ type: "SOLID", color: { r: 0.15, g: 0.15, b: 0.15 } }];
  col.appendChild(palco);
  const cam = t.camadas;
  if (!cam) {
    uploads.push({ no: palco.id, tela: t.id, arquivo: null });
  } else {
    const fundo = quadro("fundo", 0, 0, 540, 960, palco);
    fundo.locked = true;
    uploads.push({ no: fundo.id, tela: t.id, arquivo: cam.fundo });
    const nos = {};
    for (const p of cam.pecas) {
      const mae = p.pai ? cam.pecas.find((q) => q.id === p.pai) : null;
      const dentro = mae ? nos[mae.id] : palco;
      const ox = mae ? mae.x : 0, oy = mae ? mae.y : 0;
      const f = quadro(p.id, (p.x - ox) * K, (p.y - oy) * K, p.w * K, p.h * K, dentro);
      nos[p.id] = f;
      uploads.push({ no: f.id, tela: t.id, arquivo: p.arquivo });
    }
    if (cam.legenda) {
      const l = cam.legenda;
      const f = quadro("legenda", l.x * K, l.y * K, l.w * K, l.h * K, palco);
      f.locked = true;
      uploads.push({ no: f.id, tela: t.id, arquivo: l.arquivo });
    }
  }
  const st = statusAntes[t.id] || "Status: Proposta";
  col.appendChild(texto(st, 22, true, "status", { r: 0.91, g: 0.39, b: 0.24 }));
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
return { telas: telas.length, uploads };
