import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadSerif } from "@remotion/google-fonts/SourceSerif4";
import { loadFont as loadHand } from "@remotion/google-fonts/Caveat";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { useCallback } from "react";
import { useVideoConfig } from "remotion";

import tokens from "./tokens.json";

/*
 * Design system de vídeo: cores, fontes, raios e espaços vêm de tokens.json
 * (fonte única, espelhada nas variáveis do Figma). Não definir cor solta aqui
 * nem nas cenas.
 */
const opts = { subsets: ["latin", "latin-ext"] as ("latin" | "latin-ext")[] };

// os carregadores do Google Fonts precisam de import estático: o JSON escolhe qual usar
type Pesos = ("400" | "600" | "700" | "800")[];
const carregadores: Record<string, (pesos: Pesos) => string> = {
  Inter: (w) => loadInter("normal", { weights: w, ...opts }).fontFamily,
  SourceSerif4: (w) => loadSerif("normal", { weights: w as ("400" | "700")[], ...opts }).fontFamily,
  Caveat: (w) => loadHand("normal", { weights: w as "700"[], ...opts }).fontFamily,
  JetBrainsMono: (w) => loadMono("normal", { weights: w as ("400" | "700")[], ...opts }).fontFamily,
  Montserrat: (w) => loadMontserrat("normal", { weights: w, ...opts }).fontFamily,
  Anton: (w) => loadAnton("normal", { weights: w as "400"[], ...opts }).fontFamily,
};

type ChaveFonte = keyof typeof tokens.fonte;
const carregar = (k: ChaveFonte) => {
  const { familia, pesos } = tokens.fonte[k];
  const fn = carregadores[familia];
  if (!fn) throw new Error(`fonte "${familia}" (tokens.fonte.${k}) sem carregador em theme.ts`);
  return fn(pesos as Pesos);
};

export const font = {
  ui: carregar("ui"),
  serif: carregar("serif"),
  hand: carregar("hand"),
  mono: carregar("mono"),
  caption: carregar("caption"),
  stamp: carregar("stamp"),
};

export const color = tokens.cor;
export const raio = tokens.raio;
export const espaco = tokens.espaco;

export const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

/**
 * Formato da composição, pelo tamanho: story 1080×1920, feed 1080×1080, h 1920×1080.
 * Cada cena escolhe o layout com pick(f, { story, feed, h }).
 */
export type Formato = "story" | "feed" | "h";
export const useFormato = (): Formato => {
  const { width, height } = useVideoConfig();
  return height > width ? "story" : width > height ? "h" : "feed";
};
export const pick = <T,>(f: Formato, v: { story: T; feed: T; h: T }): T => v[f];

/**
 * Converte um tempo ABSOLUTO do bruto (segundos, igual à transcrição) em frame
 * local do insert que começa em `startSec`. Assim cada animação fica casada
 * com a palavra falada sem conta de cabeça.
 */
export const useAt = (startSec: number) => {
  const { fps } = useVideoConfig();
  return useCallback((absSec: number) => Math.round((absSec - startSec) * fps), [fps, startSec]);
};
