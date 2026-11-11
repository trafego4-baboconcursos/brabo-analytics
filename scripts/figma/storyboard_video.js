// Storyboard de vídeo animado no Figma (script para o use_figma do Figma MCP).
//
// Antes de colar no use_figma, troque:
//   __PAGINA__ → id da página "<COD> — Storyboard" (ex.: "1:3")
//   __DADOS__  → conteúdo de `python -m scripts.video.storyboard <resolvido> --captions … --saida out/storyboard.json
//                --camadas <output>/pecas/<COD>/story` (filtre DADOS.telas para refazer só algumas)
// Depois suba as imagens com upload_assets (nodeIds = `uploads[]` "no|arquivo", na ordem; máx. 60 por
// chamada) e POST de cada arquivo (relativo à pasta das camadas) na URL devolvida. Salve `nativos0`
// (como cada peça nativa nasceu) em out/storyboard/nativos0.json — a volta compara contra ele.
//
// REGRA (usuário, 11/11/26): texto, caixa, selo, carimbo, botão, folha, cartão, itens, medalhas e
// gráficos são camadas NATIVAS editáveis (receitas em scripts/video/receitas_figma.py); só
// ilustração, vídeo e fundo são imagem. Cada tela: cabeçalho, PALCO 540×960 (vídeo × 0,5) com
// "fundo" (travado), as peças e "legenda" (travada, por cima), Status, fala, efeitos e TEXTOS
// (só o que não dá para editar na peça, ex.: marca-texto). Nomes em português; textos editáveis
// começam com "✎". Peça filha (kicker da folha) fica dentro da mãe. Volta: storyboard_ler_camadas.js
// → storyboard.diferencas_nativas / diferencas_ajustes / diferencas_textos → lista → aplicar.
const PAGINA = "__PAGINA__";
const DADOS = __DADOS__;
const K = 0.5;

const page = await figma.getNodeByIdAsync(PAGINA);
await figma.setCurrentPageAsync(page);

// fontes: as da interface + todas as das receitas
const fontes = new Set(["Inter|Regular", "Inter|Bold"]);
const coletar = (no) => { if (no.t === "texto") fontes.add(`${no.familia}|${no.estilo}`); (no.filhos || []).forEach(coletar); };
DADOS.telas.forEach((t) => (t.camadas ? t.camadas.pecas : []).forEach((p) => p.nativo && coletar(p.nativo)));
await Promise.all([...fontes].map((f) => { const [family, style] = f.split("|"); return figma.loadFontAsync({ family, style }); }));

const rgba = (h) => ({ r: parseInt(h.slice(1, 3), 16) / 255, g: parseInt(h.slice(3, 5), 16) / 255, b: parseInt(h.slice(5, 7), 16) / 255,
  a: h.length > 7 ? parseInt(h.slice(7, 9), 16) / 255 : 1 });
const tinta = (h) => { const c = rgba(h); return { type: "SOLID", color: { r: c.r, g: c.g, b: c.b }, opacity: c.a }; };
const hexDe = (p) => "#" + [p.color.r, p.color.g, p.color.b].map((v) => Math.round(v * 255).toString(16).padStart(2, "0")).join("").toUpperCase();

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
  f.name = nome; f.resize(Math.max(1, w), Math.max(1, h)); f.x = x; f.y = y; f.fills = []; f.clipsContent = false;
  pai.appendChild(f);
  return f;
}
const CINZA = { r: 0.45, g: 0.45, b: 0.45 };

// --- desenho de uma receita (frame / texto / vetor) ------------------------------------------
function construir(no, pai) {
  const livre = !pai.layoutMode || pai.layoutMode === "NONE";
  if (no.t === "texto") {
    const t = figma.createText();
    t.fontName = { family: no.familia, style: no.estilo };
    t.characters = no.texto;
    if (no.maiusc) t.textCase = "UPPER";   // só formatação: o texto continua o da prop
    t.fontSize = no.tamanho;
    t.fills = [tinta(no.cor)];
    if (no.ls) t.letterSpacing = { value: no.ls, unit: "PIXELS" };
    if (no.lh) t.lineHeight = { value: no.lh * 100, unit: "PERCENT" };
    t.textAlignHorizontal = no.alinhar || "LEFT";
    t.name = no.rotulo || "· texto";
    for (const r of no.realce || []) t.setRangeFills(r.inicio, r.fim, [tinta(r.cor)]);
    if (no.destaque) {   // marca-texto: sublinhado grosso atrás da palavra
      const d = no.destaque, c = rgba(d.cor);
      try {
        t.setRangeTextDecoration(d.inicio, d.fim, "UNDERLINE");
        t.setRangeTextDecorationThickness(d.inicio, d.fim, { value: no.tamanho * 0.7, unit: "PIXELS" });
        t.setRangeTextDecorationOffset(d.inicio, d.fim, { value: -no.tamanho * 0.55, unit: "PIXELS" });
        t.setRangeTextDecorationColor(d.inicio, d.fim, { value: { type: "SOLID", color: { r: c.r, g: c.g, b: c.b }, opacity: c.a } });
        t.setRangeTextDecorationSkipInk(d.inicio, d.fim, false);
      } catch (e) { t.setRangeFills(d.inicio, d.fim, [tinta("#8BA800")]); }
    }
    pai.appendChild(t);
    if (no.largura) { t.textAutoResize = "HEIGHT"; t.resize(no.largura, t.height); if (!livre) t.layoutSizingHorizontal = "FILL"; }
    else if (!livre && pai.layoutMode === "HORIZONTAL" && pai.primaryAxisSizingMode === "FIXED") {
      t.layoutGrow = 1; t.textAutoResize = "HEIGHT";   // item de largura fixa: o texto quebra linha
    } else t.textAutoResize = "WIDTH_AND_HEIGHT";
    if (livre) {
      if (no.x != null) t.x = no.x;
      if (no.xd != null) t.x = no.xd - t.width;
      if (no.y != null) t.y = no.y;
    }
    return t;
  }
  if (no.t === "vetor") {
    const v = figma.createVector();
    v.name = no.nome;
    pai.appendChild(v);
    v.vectorPaths = [{ windingRule: "NONZERO", data: no.path }];
    v.fills = no.fill ? [tinta(no.fill)] : [];
    if (no.traco) {
      v.strokes = [tinta(no.traco.cor)];
      v.strokeWeight = no.traco.peso;
      v.strokeCap = "ROUND"; v.strokeJoin = "ROUND";
      if (no.traco.tracejado) { v.dashPattern = no.traco.tracejado.map((n) => n * K); v.strokeCap = "NONE"; }
    } else v.strokes = [];
    // o Figma já põe o vetor onde o path diz (normaliza a caixa para a curva): não mexer em x/y
    return v;
  }
  const f = figma.createFrame();
  f.name = no.nome;
  pai.appendChild(f);
  f.fills = no.fill ? [tinta(no.fill)] : [];
  f.clipsContent = false;
  if (no.opac != null && no.opac < 1) f.opacity = no.opac;
  if (no.raio) f.cornerRadius = no.raio;
  if (no.borda) {
    f.strokes = [tinta(no.borda.cor)];
    f.strokeAlign = "INSIDE";
    if (no.borda.lados === "baixo") { f.strokeTopWeight = 0; f.strokeLeftWeight = 0; f.strokeRightWeight = 0; f.strokeBottomWeight = no.borda.peso; }
    else f.strokeWeight = no.borda.peso;
  }
  if (no.sombra) f.effects = [{ type: "DROP_SHADOW", color: { r: 0, g: 0, b: 0, a: no.sombra.a }, offset: { x: 0, y: no.sombra.y },
    radius: no.sombra.blur, spread: 0, visible: true, blendMode: "NORMAL" }];
  if (no.auto) {
    f.layoutMode = no.auto === "H" ? "HORIZONTAL" : "VERTICAL";
    const [pt, pr, pb, pl] = no.pad;
    f.paddingTop = pt; f.paddingRight = pr; f.paddingBottom = pb; f.paddingLeft = pl;
    f.itemSpacing = no.gap || 0;
    f.counterAxisAlignItems = no.alinhar || "MIN";
    if (no.alinhar === "CENTER" && no.auto === "H" && no.w && no.h) f.primaryAxisAlignItems = "CENTER";
    if (no.auto === "V" && no.alinhar) f.counterAxisAlignItems = no.alinhar;
    f.primaryAxisSizingMode = "AUTO"; f.counterAxisSizingMode = "AUTO";
    if (no.w && no.h) { f.resize(no.w, no.h); f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED"; }
    else if (no.w) { f.resize(no.w, Math.max(1, f.height)); if (no.auto === "V") f.counterAxisSizingMode = "FIXED"; else f.primaryAxisSizingMode = "FIXED"; }
  } else {
    f.resize(Math.max(1, no.w || 1), Math.max(1, no.h || 1));
  }
  for (const filho of no.filhos || []) construir(filho, f);
  if (!no.auto) {
    // peça "· fita" e afins: dentro de frame livre, no topo/centro (fita da folha)
    for (const c of f.children) if (c.name === "· fita") { c.x = (f.width - c.width) / 2 - 20; c.y = -c.height / 2; c.rotation = 4; }
  }
  return f;
}

// coloca a peça nativa com o centro em (cx, cy) do container e a rotação do vídeo
function posicionar(f, rot, cx, cy, pai) {
  if (rot) f.rotation = rot;
  const [[, , ox], [, , oy]] = pai.absoluteTransform;
  const bb = f.absoluteBoundingBox;
  f.x += cx - (bb.x - ox + bb.width / 2);
  f.y += cy - (bb.y - oy + bb.height / 2);
}
function primeiroTexto(f) { return f.findOne((n) => n.type === "TEXT" && n.name.startsWith("✎")) || f.findOne((n) => n.type === "TEXT"); }

// --- refaz as telas que estão em DADOS (guarda Status e posição de cada uma) ------------------
const statusAntes = {}, xAntes = {};
const refazer = new Set(DADOS.telas.map((t) => t.id));
for (const n of page.findChildren((n) => n.name.startsWith("Tela · "))) {
  const id = n.name.slice(7);
  if (!refazer.has(id)) continue;
  const st = n.findOne((c) => c.name === "status" && c.type === "TEXT");
  if (st) statusAntes[id] = st.characters;
  xAntes[id] = n.x;
  n.remove();
}

const uploads = [];   // "no|arquivo" (arquivo null = still da cena, tela sem camadas)
const nativos0 = {};  // como cada peça nativa nasceu (a volta compara contra isso)
DADOS.telas.forEach((t, i) => {
  const col = figma.createAutoLayout("VERTICAL", { name: `Tela · ${t.id}`, itemSpacing: 16 });
  col.x = xAntes[t.id] ?? i * 620;
  col.y = 0;
  page.appendChild(col);
  col.appendChild(texto(`${Math.round(col.x / 620) + 1}. ${t.id} · ${t.componente} · ${t.de}s → ${t.ate}s`, 24, true, "cabeçalho"));
  const palco = figma.createFrame();
  palco.name = "palco"; palco.resize(540, 960); palco.clipsContent = true;
  palco.fills = [{ type: "SOLID", color: { r: 0.15, g: 0.15, b: 0.15 } }];
  col.appendChild(palco);
  const cam = t.camadas;
  if (!cam) {
    uploads.push(`${palco.id}|null`);
  } else {
    const fundo = quadro("fundo", 0, 0, 540, 960, palco);
    fundo.locked = true;
    uploads.push(`${fundo.id}|${cam.fundo}`);
    const nos = {};
    for (const p of cam.pecas) {
      const mae = p.pai ? cam.pecas.find((q) => q.id === p.pai) : null;
      const dentro = mae ? nos[mae.id] : palco;
      if (p.nativo) {
        const f = construir({ ...p.nativo, nome: p.nome || p.id }, dentro);
        // centro no container: no palco, pv × K; dentro da mãe, relativo ao canto dela (sem girar)
        let cx = p.nativo.pv[0] * K, cy = p.nativo.pv[1] * K;
        if (mae && mae.nativo) { cx -= mae.nativo.pv[0] * K - nos[mae.id].width / 2; cy -= mae.nativo.pv[1] * K - nos[mae.id].height / 2; }
        else if (mae) { cx -= mae.x * K; cy -= mae.y * K; }
        posicionar(f, p.nativo.rot, cx, cy, dentro);
        nos[p.id] = f;
        const [[, , ox], [, , oy]] = dentro.absoluteTransform;
        const bb = f.absoluteBoundingBox;
        const tx = primeiroTexto(f);
        (nativos0[t.id] ||= {})[p.id] = {
          cx: bb.x - ox + bb.width / 2, cy: bb.y - oy + bb.height / 2, largura: f.width, altura: f.height,
          rot: f.rotation, fonte: tx ? tx.fontSize : 1, pv: p.nativo.pv, ancora: p.nativo.ancora,
          cores: p.nativo.cores, cor0: f.fills[0] ? hexDe(f.fills[0]) : null, corTexto0: tx ? hexDe(tx.getRangeFills(0, 1)[0]) : null,
        };
        continue;
      }
      const ox = mae ? mae.x : 0, oy = mae ? mae.y : 0;
      const f = quadro(p.nome || p.id, (p.x - ox) * K, (p.y - oy) * K, p.w * K, p.h * K, dentro);
      nos[p.id] = f;
      uploads.push(`${f.id}|${p.arquivo}`);
    }
    if (cam.legenda) {
      const l = cam.legenda;
      const f = quadro("legenda", l.x * K, l.y * K, l.w * K, l.h * K, palco);
      f.locked = true;
      uploads.push(`${f.id}|${l.arquivo}`);
    }
  }
  col.appendChild(texto(statusAntes[t.id] || "Status: Proposta", 22, true, "status", { r: 0.91, g: 0.39, b: 0.24 }));
  for (const [rot, val] of [["Fala", t.fala], ["Efeitos", t.efeitos.join(" · ") || "—"]]) {
    col.appendChild(texto(rot.toUpperCase(), 14, true, `rótulo ${rot}`, CINZA));
    const v = texto(val, 18, false, rot.toLowerCase());
    v.textAutoResize = "HEIGHT"; v.resize(540, v.height);
    col.appendChild(v);
  }
  if (Object.keys(t.textos).length) {
    col.appendChild(texto("OUTROS TEXTOS — edite o texto em negrito (o resto se edita direto na tela)", 14, true, "rótulo textos", CINZA));
    const grupo = figma.createAutoLayout("VERTICAL", { name: "textos", itemSpacing: 10 });
    col.appendChild(grupo);
    for (const [caminho, valor] of Object.entries(t.textos)) {
      const nome = (t.rotulos && t.rotulos[caminho]) || caminho;
      grupo.appendChild(texto(nome, 12, false, `rótulo ${nome}`, CINZA));
      const v = texto(valor, 20, true, nome);
      v.textAutoResize = "HEIGHT"; v.resize(540, v.height);
      grupo.appendChild(v);
    }
  }
});
return { telas: DADOS.telas.length, uploads, nativos0 };
