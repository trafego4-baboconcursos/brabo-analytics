/*
 * Contrato das cenas. Todo texto e todo tempo vem das props; os tempos são
 * SEGUNDOS ABSOLUTOS do bruto (os mesmos da transcrição), para casar com a fala.
 * Quebra de linha manual: "\n" no texto (renderizado com white-space: pre-line).
 */

/** Intervalo [início, fim] em segundos absolutos. */
export type Intervalo = [number, number];
/** Texto que entra num instante da fala. */
export type TextoEm = { texto: string; em: number };

export type PropsDesenho = {
  img: string;
  /** vídeo animado gerado a partir da ilustração (public/), no lugar da imagem; o 1º quadro é a img */
  video?: string;
  /** x/y/rot só valem no story (no feed/h as etiquetas empilham na coluna) */
  /** cor/corTexto: opcionais (padrão ink/paper); vêm do balão caixa + lettering do storyboard */
  etiquetas: { texto: string; em: number; x: number; y: number; rot: number; cor?: string; corTexto?: string }[];
};

export type PropsManchete = {
  kicker: string;
  titulo: string;
  /** corpo completo; `destaque.texto` precisa aparecer dentro dele */
  corpo: string;
  destaque: TextoEm;
};

export type PropsGrafico = {
  kicker: string;
  prefixo: string;
  valorFinal: number;
  /** valores dos degraus da curva (o 1º é o valor inicial) */
  pontos: number[];
  /** [mín, máx] do eixo; padrão: 90% do menor ponto → 125% do maior */
  escala?: [number, number];
  eixo: [string, string];
  rotuloFim: { valor: string; sub: string };
  selo: string;
  em: { conta: Intervalo; linha: Intervalo; rotulo: number; selo: number };
};

export type PropsCarimbo = {
  kicker: string;
  pergunta: string;
  carimbo: TextoEm;
  corpo: string;
  destaque: TextoEm;
  mao: TextoEm;
};

export type PropsRota = {
  imagem: string;
  /** tamanho original da imagem (para o encaixe "cover" em 1080×1920) */
  imagemTamanho: [number, number];
  /** coordenadas no canvas 1080×1920 do story */
  estrada: [number, number][];
  trilha: [number, number][];
  cume: { x: number; y: number };
  kicker: string;
  titulo: string;
  tituloDestaque: TextoEm;
  selo: TextoEm;
  rotuloCume: string;
  em: { estrada: Intervalo; trilha: Intervalo; bandeira: number; saiTitulo: number };
};

export type PropsPapelMesa = {
  kicker: string;
  titulo: string;
  curvaRuim: { rotulo: string; em: Intervalo };
  curvaBoa: { rotulo: string; em: Intervalo };
  circulo: { em: number };
  mao: TextoEm;
  adesivo: TextoEm;
};

export type PropsCartao = {
  kicker: string;
  /** "\n" quebra a linha no story/feed; no horizontal vira espaço */
  titulo: string;
  subtitulo: TextoEm;
  carimbo: TextoEm;
};

export type PropsChecklist = {
  kicker: string;
  titulo: string;
  itens: TextoEm[];
  /** o último item ganha fundo coral */
  destacarUltimo: boolean;
};

export type PropsContador = {
  kicker: string;
  numero: number;
  /** "\n" permitido */
  rotulo: string;
  conta: Intervalo;
  medalhas: { quantidade: number; marca: string; texto: string; em: number };
};

/** `imagem`: elemento-herói opcional (ex.: PNG 3D do Blender com fundo transparente, em public/). */
export type PropsSplash = { titulo: string; subtitulo?: string; em: number; imagem?: string };

export type PropsCta = { titulo: string; subtitulo: string; chamada: TextoEm };

/** Bloco de conteúdo do Painel (estilo "noite" do AD359). Tempos em segundos absolutos. */
export type BlocoPainel =
  | { tipo: "contador"; de?: number; ate: number; prefixo?: string; sufixo?: string; rotulo: string; conta: Intervalo }
  | { tipo: "barras"; itens: { rotulo: string; valor: string; fracao: number; cor?: "amarelo" | "verde" | "vermelho"; em: number }[] }
  | { tipo: "ordem"; itens: { texto: string; em: number; ok?: boolean }[] }
  | { tipo: "lista"; itens: { texto: string; em: number; ok?: boolean }[] }
  | { tipo: "carimbo"; texto: string; em: number };

/**
 * Painel "noite": ilustração chapada de fundo (`fundo`, em public/, gerada por IA), HUD com
 * `hud` (pílula com ponto vermelho, opcional) e `tag` (assunto, amarela), `titulo` com a palavra
 * `destaque` em amarelo, e um `bloco` de conteúdo.
 */
export type PropsPainel = {
  fundo?: string;
  hud?: string;
  tag: string;
  titulo?: { texto: string; destaque?: string; em: number };
  bloco: BlocoPainel;
};

export type PropsPorCena = {
  Desenho: PropsDesenho;
  Manchete: PropsManchete;
  Grafico: PropsGrafico;
  Carimbo: PropsCarimbo;
  Rota: PropsRota;
  PapelMesa: PropsPapelMesa;
  Cartao: PropsCartao;
  Checklist: PropsChecklist;
  Contador: PropsContador;
  Splash: PropsSplash;
  Cta: PropsCta;
  Painel: PropsPainel;
};

export type NomeCena = keyof PropsPorCena;

/** O que toda cena recebe: início/duração da cena + as props do seu tipo. */
export type PropsCena<N extends NomeCena> = { start: number; dur: number; props: PropsPorCena[N] };
