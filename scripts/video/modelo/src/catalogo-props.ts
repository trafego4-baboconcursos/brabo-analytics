import type { PropsPorCena } from "./cenas/tipos";

/*
 * Catálogo de verificação: cada cena com o TEXTO MAIS LONGO esperado em cada
 * campo, para ver se algo estoura no story, no feed ou no horizontal.
 * Tempos relativos a uma cena que começa em 0 s e dura DUR_CATALOGO; o still
 * é tirado no fim, com tudo já na tela.
 */
export const DUR_CATALOGO = 4;

export const CATALOGO: { [N in keyof PropsPorCena]: PropsPorCena[N] } = {
  Desenho: {
    img: "dona-de-casa-original.jpg",
    etiquetas: [
      { texto: "trabalha o dia inteiro", em: 0.2, x: 90, y: 190, rot: -4 },
      { texto: "cuida da casa e dos filhos", em: 0.4, x: 330, y: 290, rot: 3 },
      { texto: "pouco tempo pra estudar", em: 0.6, x: 120, y: 390, rot: -2 },
    ],
  },
  Manchete: {
    kicker: "Ficha do concurso · Tribunal de Justiça",
    titulo: "Escrevente Técnico Judiciário", // 32 caracteres
    corpo: "Cargo do Tribunal de Justiça de São Paulo. Exige só nível médio: não precisa de faculdade.",
    destaque: { texto: "nível médio", em: 0.5 },
  },
  Grafico: {
    kicker: "SALÁRIO INICIAL · TÉCNICO DO SEGURO SOCIAL",
    prefixo: "R$",
    valorFinal: 17234,
    pontos: [7234, 7234, 7700, 7700, 8300, 8300, 9000, 9000, 9900, 9900, 11000],
    eixo: ["INÍCIO", "FINAL DE CARREIRA"],
    rotuloFim: { valor: "≈ R$ 11 mil", sub: "CARREIRA FEDERAL" },
    selo: "✓ Estabilidade garantida por lei federal",
    em: { conta: [0.2, 1.0], linha: [1.0, 2.0], rotulo: 2.0, selo: 2.4 },
  },
  Carimbo: {
    kicker: "Concurso INSS · situação hoje",
    pergunta: "O edital já foi publicado?",
    carimbo: { texto: "AINDA NÃO", em: 0.4 },
    corpo: "Está aguardando autorização do governo para um novo concurso.",
    destaque: { texto: "aguardando autorização", em: 0.8 },
    mao: { texto: "→ dá tempo de se preparar!", em: 1.2 },
  },
  Rota: {
    imagem: "mapa-montanha-limpo.jpg",
    imagemTamanho: [1536, 2752],
    estrada: [[120, 1840], [245, 1680], [205, 1520], [450, 1390], [405, 1220], [615, 1090], [560, 968]],
    trilha: [[560, 968], [420, 880], [470, 820], [400, 760], [452, 690], [470, 545], [478, 405]],
    cume: { x: 478, y: 402 },
    kicker: "ROTA ATÉ A APROVAÇÃO",
    titulo: "Preparação de médio e longo prazo",
    tituloDestaque: { texto: "médio e longo prazo", em: 0.3 },
    selo: { texto: "⏱ 2h por dia, todo dia", em: 1.6 },
    rotuloCume: "Aprovação",
    em: { estrada: [0.2, 1.4], trilha: [1.6, 2.6], bandeira: 2.7, saiTitulo: 2.3 },
  },
  PapelMesa: {
    kicker: "Por que tanta gente estuda e não passa",
    titulo: "Mesmas 2h por dia, resultados opostos",
    curvaRuim: { rotulo: "sem método", em: [0.2, 0.8] },
    curvaBoa: { rotulo: "método certo", em: [0.9, 1.6] },
    circulo: { em: 1.8 },
    mao: { texto: "evolui muito mais rápido", em: 2.0 },
    adesivo: { texto: "O MÉTODO", em: 1.0 },
  },
  Cartao: {
    kicker: "✳ CURSO DO MATEUS",
    titulo: "Projeto\nINSS",
    subtitulo: { texto: "Como estudar para ser aprovada no INSS", em: 0.6 },
    carimbo: { texto: "GRATUITO", em: 0.4 },
  },
  Checklist: {
    kicker: "NO PROJETO INSS",
    titulo: "Você vai aprender",
    itens: [
      { texto: "Como organizar todas as matérias", em: 0.2 }, // 32
      { texto: "Quanto tempo estudar cada matéria", em: 0.5 }, // 34
      { texto: "As matérias mais importantes", em: 0.8 },
      { texto: "O Método Ativo 5x", em: 1.1 },
    ],
    destacarUltimo: true,
  },
  Contador: {
    kicker: "RESULTADO DO MÉTODO ATIVO 5X",
    numero: 16,
    rotulo: "aprovações\nem concurso",
    conta: [0.2, 1.0],
    medalhas: { quantidade: 2, marca: "1º", texto: "duas em\n1º lugar", em: 1.2 },
  },
  Splash: { titulo: "Concurso do INSS", subtitulo: "2h por dia é suficiente?", em: 0.2 },
  Cta: {
    titulo: "Cadastro gratuito",
    subtitulo: "Projeto INSS · grupo no WhatsApp",
    chamada: { texto: "toque no botão ↓", em: 0.6 },
  },
};
