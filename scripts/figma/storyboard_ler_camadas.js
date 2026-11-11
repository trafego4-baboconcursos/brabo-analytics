// Volta do storyboard em camadas (script para o use_figma). Troque __PAGINA__ pelo id da página.
// Devolve, por tela, o Status e cada peça como o usuário deixou, no formato que
// scripts/video/storyboard.py:diferencas_ajustes espera:
//   camadas[tela][peça] = { cx, cy, largura, rot }
// cx/cy = centro da caixa no frame que contém a peça (palco, ou a mãe para peça filha) — o
// centro não muda ao girar; largura = largura sem rotação; rot = rotação do Figma (graus).
// Também devolve os textos editáveis (camadas TEXT do grupo "textos") para diferencas_textos.
const PAGINA = "__PAGINA__";
const page = await figma.getNodeByIdAsync(PAGINA);
const FIXAS = new Set(["fundo", "legenda"]);
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
      if (FIXAS.has(n.name) || n.type !== "FRAME") continue;
      const bb = n.absoluteBoundingBox;
      camadas[n.name] = {
        cx: Math.round((bb.x + bb.width / 2 - ox) * 100) / 100,
        cy: Math.round((bb.y + bb.height / 2 - oy) * 100) / 100,
        largura: Math.round(n.width * 100) / 100,
        rot: Math.round(n.rotation * 10) / 10,
      };
      // caixa + lettering: texto vivo, tamanho da letra e cores (storyboard.diferencas_nativas)
      const t = n.children && n.children.find((c) => c.type === "TEXT" && c.name === "texto");
      if (t) {
        const h = (p) => "#" + [p.color.r, p.color.g, p.color.b].map((v) => Math.round(v * 255).toString(16).padStart(2, "0")).join("").toUpperCase();
        Object.assign(camadas[n.name], { texto: t.characters, fonte: t.fontSize, cor: h(n.fills[0]), corTexto: h(t.fills[0]) });
        continue;
      }
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
return saida;
