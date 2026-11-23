// Separa a captura de uma tela do painel (generate_figma_design) em blocos numa pilha em auto layout ("Blocos"),
// cada bloco com "Atual" (não editar) e "Proposta" (editar) lado a lado. Quando a Proposta cresce, os blocos de
// baixo descem sozinhos (antes eram Sections com posição fixa e uma invadia a outra). Rodar via use_figma,
// trocando PAGE_ID e ROOT_ID (nó devolvido pela captura). Ver FIGMA_PRODUCAO_DE_ARTE.md, seção 10.
// Blocos com o mesmo título ganham o texto que só eles têm (ex.: "Ranking de Anúncios — Meta").
// Depois conferir a lista: KPIs viram "R$ ...", a barra de seções vira "Buscar seção..." — renomear à mão.
const PAGE_ID = '__PAGE__', ROOT_ID = '__ROOT__';
const page = await figma.getNodeByIdAsync(PAGE_ID); await figma.setCurrentPageAsync(page);
await figma.loadFontAsync({ family: 'Inter', style: 'Regular' }); await figma.loadFontAsync({ family: 'Inter', style: 'Bold' });
const full = await figma.getNodeByIdAsync(ROOT_ID);
full.name = 'Página inteira — no ar (referência)'; full.x = 0; full.y = 0;
// desce pelo filho mais alto até achar o contêiner que tem os blocos (≥3 filhos)
let content = full;
for (let d = 0; d < 6; d++) {
  const kids = (content.children || []).filter(c => c.visible !== false);
  if (kids.length >= 3 && content !== full) break;
  const t = kids.sort((a, b) => b.height - a.height)[0];
  if (!t || !('children' in t)) break;
  content = t;
}
const letra = /[A-Za-zÀ-ú]/;
const textos = b => b.findAllWithCriteria({ types: ['TEXT'] }).map(t => t.characters.trim().replace(/\s+/g, ' ')).filter(x => letra.test(x));
const blocos = content.children.filter(c => c.visible !== false && c.height >= 40);
const nomes = blocos.map(b => {
  const ts = textos(b); let n = (ts[0] || b.name).slice(0, 60);
  if (n.length < 4 || /^(recolher|expandir)$/i.test(n)) { const l = ts.find(x => x.length >= 8 && !/^(recolher|expandir)/i.test(x)); if (l) n = l.slice(0, 60); }
  return n;
});
const lists = blocos.map(b => textos(b).filter(x => x.length <= 40).slice(0, 25));
const grupos = {}; nomes.forEach((n, i) => (grupos[n] = grupos[n] || []).push(i));
for (const [n, idx] of Object.entries(grupos)) {
  if (idx.length < 2) continue;
  for (const i of idx) {
    const others = new Set(idx.filter(j => j !== i).flatMap(j => lists[j]));
    const d = lists[i].find(x => !others.has(x) && !n.includes(x));
    if (d) nomes[i] = n + ' — ' + d;
  }
}
const pilha = figma.createAutoLayout('VERTICAL', { name: 'Blocos', itemSpacing: 160 }); pilha.fills = [];
page.appendChild(pilha); pilha.x = full.width + 400; pilha.y = 0;
const CINZA = { r: 0.949, g: 0.953, b: 0.961 }; const out = [];
const label = (t, c) => { const x = figma.createText(); x.fontName = { family: 'Inter', style: 'Bold' }; x.characters = t; x.fontSize = 20; x.fills = [{ type: 'SOLID', color: c }]; return x; };
blocos.forEach((src, k) => {
  const bloco = figma.createAutoLayout('HORIZONTAL', { name: String(k + 1).padStart(2, '0') + ' · ' + nomes[k], itemSpacing: 120 });
  bloco.paddingTop = bloco.paddingBottom = bloco.paddingLeft = bloco.paddingRight = 80;
  bloco.fills = [{ type: 'SOLID', color: CINZA }]; bloco.cornerRadius = 8; pilha.appendChild(bloco);
  const colA = figma.createAutoLayout('VERTICAL', { name: 'col Atual', itemSpacing: 24 }); colA.fills = [];
  const colB = figma.createAutoLayout('VERTICAL', { name: 'col Proposta', itemSpacing: 24 }); colB.fills = [];
  bloco.appendChild(colA); bloco.appendChild(colB);
  const cab = figma.createAutoLayout('HORIZONTAL', { name: 'cabeçalho', itemSpacing: 24, counterAxisAlignItems: 'CENTER' }); cab.fills = [];
  colA.appendChild(label('ATUAL — no ar (não editar)', { r: 0.42, g: 0.447, b: 0.502 }));
  colB.appendChild(cab); cab.appendChild(label('PROPOSTA — editar aqui', { r: 0.184, g: 0.369, b: 0.89 }));
  const a = src.clone(), b = src.clone(); a.name = 'Atual'; b.name = 'Proposta';
  colA.appendChild(a); colB.appendChild(b);
  if (b.layoutMode === 'VERTICAL') b.primaryAxisSizingMode = 'AUTO'; else if (b.layoutMode === 'HORIZONTAL') b.counterAxisSizingMode = 'AUTO';
  out.push(bloco.name);
});
return out;
