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
//   em português — "Título", "Balão 1 · trabalha" — e "legenda" (travada, por cima). Peça filha (kicker da folha) fica
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
const hex = (h) => ({ r: parseInt(h.slice(1, 3), 16) / 255, g: parseInt(h.slice(3, 5), 16) / 255, b: parseInt(h.slice(5, 7), 16) / 255 });
await figma.loadFontAsync({ family: "Inter", style: "Extra Bold" });

// Caixa + lettering: a peça vira um frame de auto layout com o texto vivo dentro ("texto").
// O usuário digita no balão, troca a cor da caixa/letra e o tamanho da letra; a caixa cresce
// junto. Centro em (cx, cy) do palco e rotação do vídeo. Devolve como ficou (nativos0).
function caixaNativa(nome, n, pai) {
  const f = figma.createFrame();
  f.name = nome;
  f.layoutMode = "HORIZONTAL";
  f.primaryAxisSizingMode = "AUTO";
  f.counterAxisSizingMode = "AUTO";
  f.paddingTop = f.paddingBottom = n.padV;
  f.paddingLeft = f.paddingRight = n.padH;
  f.cornerRadius = n.raio;
  f.fills = [{ type: "SOLID", color: hex(n.cor) }];
  f.effects = [{ type: "DROP_SHADOW", color: { r: 0, g: 0, b: 0, a: 0.3 }, offset: { x: 0, y: 7 }, radius: 15,
    spread: 0, visible: true, blendMode: "NORMAL" }];
  const t = figma.createText();
  t.name = "texto";
  t.fontName = { family: "Inter", style: "Extra Bold" };
  t.fontSize = n.fonte;
  t.characters = n.texto;
  t.fills = [{ type: "SOLID", color: hex(n.corTexto) }];
  f.appendChild(t);
  pai.appendChild(f);
  f.rotation = n.rot;
  const [[, , ox], [, , oy]] = pai.absoluteTransform;
  const bb = f.absoluteBoundingBox;
  f.x += n.cx - (bb.x - ox + bb.width / 2);
  f.y += n.cy - (bb.y - oy + bb.height / 2);
  return f;
}

// idempotente: refaz só as telas que estão em DADOS (as outras ficam como estão), guardando o
// Status e a posição de cada uma. Para refazer só algumas, filtre DADOS.telas antes de colar.
const statusAntes = {};
const xAntes = {};
const refazer = new Set(DADOS.telas.map((t) => t.id));
for (const n of page.findChildren((n) => n.name.startsWith("Tela · "))) {
  const id = n.name.slice(7);
  if (!refazer.has(id)) continue;
  const st = n.findOne((c) => c.name === "status" && c.type === "TEXT");
  if (st) statusAntes[id] = st.characters;
  xAntes[id] = n.x;
  n.remove();
}

const telas = [];
const uploads = []; // { no, arquivo } — arquivo null = still da cena (tela sem camadas)
const nativos0 = {}; // caixas + lettering como foram criadas → salvar em nativos0.json (volta)
DADOS.telas.forEach((t, i) => {
  const col = figma.createAutoLayout("VERTICAL", { name: `Tela · ${t.id}`, itemSpacing: 16 });
  col.x = xAntes[t.id] ?? i * 620;
  col.y = 0;
  page.appendChild(col);
  col.appendChild(texto(`${Math.round(col.x / 620) + 1}. ${t.id} · ${t.componente} · ${t.de}s → ${t.ate}s`, 24, true, "cabeçalho"));
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
      // nome em português ("Balão 1 · trabalha"); a volta traduz de novo (storyboard.nome_camada)
      if (p.nativo) {
        const f = caixaNativa(p.nome || p.id, p.nativo, dentro);
        nos[p.id] = f;
        (nativos0[t.id] ||= {})[p.id] = { largura: f.width, rot: f.rotation, fonte: p.nativo.fonte };
        continue;
      }
      const f = quadro(p.nome || p.id, (p.x - ox) * K, (p.y - oy) * K, p.w * K, p.h * K, dentro);
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
  col.appendChild(texto("TEXTOS — edite o texto em negrito (não renomeie as camadas)", 14, true, "rótulo textos", CINZA));
  const grupo = figma.createAutoLayout("VERTICAL", { name: "textos", itemSpacing: 10 });
  col.appendChild(grupo);
  for (const [caminho, valor] of Object.entries(t.textos)) {
    const nome = (t.rotulos && t.rotulos[caminho]) || caminho;
    grupo.appendChild(texto(nome, 12, false, `rótulo ${nome}`, CINZA));
    const v = texto(valor, 20, true, nome);
    v.textAutoResize = "HEIGHT";
    v.resize(540, v.height);
    grupo.appendChild(v);
  }
  telas.push(col.id);
});
return { telas: telas.length, uploads, nativos0 };
