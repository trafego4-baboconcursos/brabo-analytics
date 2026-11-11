import React from "react";
import { Carimbo } from "../cenas/Carimbo";
import { Cartao } from "../cenas/Cartao";
import { Checklist } from "../cenas/Checklist";
import { Contador } from "../cenas/Contador";
import { Cta } from "../cenas/Cta";
import { Desenho } from "../cenas/Desenho";
import { Grafico } from "../cenas/Grafico";
import { Manchete } from "../cenas/Manchete";
import { PapelMesa } from "../cenas/PapelMesa";
import { Rota } from "../cenas/Rota";

/*
 * As animações do AD368 como instâncias da biblioteca de cenas (src/cenas/).
 * Só props: textos e tempos (segundos absolutos do bruto). Serve de gabarito
 * de regressão até a Tarefa 3 trocar isto pelo criativo.json.
 */
type P = { start: number; dur: number };

export const DonaDeCasa: React.FC<P> = (p) => (
  <Desenho {...p} props={{ img: "dona-de-casa-original.jpg", etiquetas: [
    { texto: "trabalha", em: 4.4, x: 90, y: 190, rot: -4 },
    { texto: "cuida da casa", em: 4.82, x: 430, y: 290, rot: 3 },
    { texto: "pouco tempo pra estudar", em: 6.25, x: 120, y: 390, rot: -2 },
  ] }} />
);

export const SemFaculdade: React.FC<P> = (p) => (
  <Desenho {...p} props={{ img: "dona-de-casa-faculdade.jpg", etiquetas: [
    { texto: "faculdade? não", em: 19.66, x: 40, y: 150, rot: -4 },
    { texto: "só ensino médio", em: 20.8, x: 520, y: 310, rot: 3 },
  ] }} />
);

export const TemFilho: React.FC<P> = (p) => (
  <Desenho {...p} props={{ img: "dona-de-casa-filho.jpg", etiquetas: [
    { texto: "trabalha", em: 53.82, x: 90, y: 190, rot: -4 },
    { texto: "cuida da casa", em: 54.28, x: 430, y: 290, rot: 3 },
    { texto: "tem filho", em: 55.12, x: 160, y: 390, rot: -2 },
  ] }} />
);

export const CargoManchete: React.FC<P> = (p) => (
  <Manchete {...p} props={{
    kicker: "Ficha do concurso · INSS",
    titulo: "Técnico do Seguro Social",
    corpo: "Cargo da autarquia federal. Exige só nível médio: não precisa de faculdade.",
    destaque: { texto: "nível médio", em: 32.4 },
  }} />
);

export const SalarioGrafico: React.FC<P> = (p) => (
  <Grafico {...p} props={{
    kicker: "SALÁRIO INICIAL · TÉCNICO DO INSS",
    prefixo: "R$",
    valorFinal: 7234,
    pontos: [7234, 7234, 7700, 7700, 8300, 8300, 9000, 9000, 9900, 9900, 11000],
    escala: [6500, 13800],
    eixo: ["INÍCIO", "FINAL DE CARREIRA"],
    rotuloFim: { valor: "≈ R$ 11 mil", sub: "CARREIRA FEDERAL" },
    selo: "✓ Estabilidade garantida por lei",
    em: { conta: [34.1, 35.5], linha: [36.1, 38.9], rotulo: 38.5, selo: 40.9 },
  }} />
);

export const StatusCarimbo: React.FC<P> = (p) => (
  <Carimbo {...p} props={{
    kicker: "Concurso INSS · situação hoje",
    pergunta: "O edital já saiu?",
    carimbo: { texto: "AINDA NÃO", em: 46.1 },
    corpo: "Está aguardando autorização para um novo concurso.",
    destaque: { texto: "aguardando autorização", em: 47.4 },
    mao: { texto: "→ dá tempo de se preparar!", em: 49.6 },
  }} />
);

export const RotaMapa: React.FC<P> = (p) => (
  <Rota {...p} props={{
    imagem: "mapa-montanha-limpo.jpg",
    imagemTamanho: [1536, 2752],
    estrada: [
      [120, 1840], [200, 1790], [245, 1750], [245, 1680], [225, 1600], [205, 1520], [215, 1480], [280, 1445],
      [380, 1410], [450, 1390], [455, 1350], [430, 1280], [405, 1220], [410, 1180], [480, 1150], [580, 1120],
      [615, 1090], [600, 1040], [575, 1000], [560, 968],
    ],
    trilha: [[560, 968], [505, 935], [420, 880], [470, 820], [400, 760], [452, 690], [425, 620], [470, 545], [478, 405]],
    cume: { x: 478, y: 402 },
    kicker: "ROTA ATÉ A APROVAÇÃO",
    titulo: "Preparação de médio e longo prazo",
    tituloDestaque: { texto: "médio e longo prazo", em: 65.4 },
    selo: { texto: "⏱ 2h por dia", em: 70.3 },
    rotuloCume: "Aprovação",
    em: { estrada: [63.3, 68.9], trilha: [70.9, 73.7], bandeira: 73.75, saiTitulo: 73.2 },
  }} />
);

export const MetodoMesa: React.FC<P> = (p) => (
  <PapelMesa {...p} props={{
    kicker: "Por que tanta gente estuda e não passa",
    titulo: "Mesmas 2h por dia, resultados opostos",
    curvaRuim: { rotulo: "sem método", em: [86.2, 87.8] },
    curvaBoa: { rotulo: "método certo", em: [89.7, 91.0] },
    circulo: { em: 91.7 },
    mao: { texto: "evolui mais rápido", em: 91.9 },
    adesivo: { texto: "O MÉTODO", em: 89.5 },
  }} />
);

export const ProjetoCard: React.FC<P> = (p) => (
  <Cartao {...p} props={{
    kicker: "✳ CURSO DO MATEUS",
    titulo: "Projeto\nINSS",
    subtitulo: { texto: "Como estudar para ser aprovada", em: 104.6 },
    carimbo: { texto: "GRATUITO", em: 103.3 },
  }} />
);

export const ChecklistCurso: React.FC<P> = (p) => (
  <Checklist {...p} props={{
    kicker: "NO PROJETO INSS",
    titulo: "Você vai aprender",
    itens: [
      { texto: "Como organizar as matérias", em: 110.9 },
      { texto: "Quanto tempo estudar cada uma", em: 112.0 },
      { texto: "As matérias mais importantes", em: 114.5 },
      { texto: "O Método Ativo 5x", em: 117.1 },
    ],
    destacarUltimo: true,
  }} />
);

export const Aprovacoes: React.FC<P> = (p) => (
  <Contador {...p} props={{
    kicker: "RESULTADO DO MÉTODO ATIVO 5X",
    numero: 6,
    rotulo: "aprovações\nem concurso",
    conta: [120.4, 121.2],
    medalhas: { quantidade: 2, marca: "1º", texto: "duas em\n1º lugar", em: 122.3 },
  }} />
);

export const CtaFinal: React.FC<P> = (p) => (
  <Cta {...p} props={{
    titulo: "Cadastro gratuito",
    subtitulo: "Projeto INSS · grupo no WhatsApp",
    chamada: { texto: "toque no botão ↓", em: 135.6 },
  }} />
);
