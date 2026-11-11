// Volta do storyboard em camadas (script para o use_figma). Troque __PAGINA__ pelo id da página.
// Devolve, por tela, o Status e cada peça como o usuário deixou:
//   camadas[tela][peça] = { cx, cy, largura, rot }                       ← peça imagem
//   camadas[tela][peça] = { cx, cy, largura, altura, rot, fonte, textos, cor, corTexto } ← nativa
// cx/cy = centro da caixa no frame que contém a peça (palco, ou a mãe para peça filha) — o centro
// não muda ao girar. Nativa: textos = { "✎ rótulo": texto } das camadas de texto dela (não das
// filhas); fonte = tamanho do 1º texto ✎; cor = fundo da peça; corTexto = cor do 1º texto ✎.
// → storyboard.diferencas_ajustes (imagens), diferencas_nativas (nativas), diferencas_textos
// (grupo "textos" da tela).
const PAGINA = "__PAGINA__";
const page = await figma.getNodeByIdAsync(PAGINA);
const FIXAS = new Set(["fundo", "legenda"]);
const hexDe = (p) => "#" + [p.color.r, p.color.g, p.color.b].map((v) => Math.round(v * 255).toString(16).padStart(2, "0")).join("").toUpperCase();
const ehPeca = (n) => n.type === "FRAME" && !FIXAS.has(n.name) && !n.name.startsWith("·");
const ehImagem = (n) => n.fills && n.fills.length && n.fills[0].type === "IMAGE";

// textos ✎ da peça, sem entrar nas peças filhas
function textosDe(f, saida = []) {
  for (const c of f.children || []) {
    if (c.type === "TEXT" && c.name.startsWith("✎")) saida.push(c);
    else if (c.type === "FRAME" && !ehPeca(c)) textosDe(c, saida);
  }
  return saida;
}

const saida = { status: {}, camadas: {}, textos: {} };
for (const col of page.findChildren((n) => n.name.startsWith("Tela · "))) {
  const tela = col.name.slice(7);
  const st = col.findOne((c) => c.name === "status" && c.type === "TEXT");
  saida.status[tela] = st ? st.characters : null;
  const palco = col.findOne((c) => c.name === "palco");
  const camadas = {};
  const visitar = (container) => {
    const [[, , ox], [, , oy]] = container.absoluteTransform;
    for (const n of container.children || []) {
      if (!ehPeca(n)) continue;
      const bb = n.absoluteBoundingBox;
      const c = { cx: Math.round((bb.x + bb.width / 2 - ox) * 100) / 100, cy: Math.round((bb.y + bb.height / 2 - oy) * 100) / 100,
        largura: Math.round(n.width * 100) / 100, rot: Math.round(n.rotation * 10) / 10 };
      if (!ehImagem(n)) {
        const ts = textosDe(n);
        Object.assign(c, {
          altura: Math.round(n.height * 100) / 100, fonte: ts[0] ? ts[0].fontSize : 1,
          textos: Object.fromEntries(ts.map((t) => [t.name, t.characters])),
          cor: n.fills && n.fills[0] && n.fills[0].type === "SOLID" ? hexDe(n.fills[0]) : null,
          corTexto: ts[0] ? hexDe(ts[0].getRangeFills(0, 1)[0]) : null,
        });
      }
      camadas[n.name] = c;
      visitar(n);
    }
  };
  if (palco) visitar(palco);
  if (Object.keys(camadas).length) saida.camadas[tela] = camadas;
  const grupo = col.findOne((c) => c.name === "textos");
  if (grupo) {
    saida.textos[tela] = {};
    for (const n of grupo.children) if (n.type === "TEXT" && !n.name.startsWith("rótulo ")) saida.textos[tela][n.name] = n.characters;
  }
}
return JSON.stringify(saida);
