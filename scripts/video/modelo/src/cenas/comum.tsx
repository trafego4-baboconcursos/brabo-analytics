import { Easing, interpolate, useVideoConfig } from "remotion";
import { clamp, color } from "../theme";

export const ease = Easing.bezier(0.16, 1, 0.3, 1);

/** Entrada padrão de um elemento: fade + sobe 24 px. */
export const appear = (frame: number, at: number) => ({
  opacity: interpolate(frame, [at, at + 8], [0, 1], clamp),
  translate: interpolate(frame, [at, at + 12], ["0px 24px", "0px 0px"], { ...clamp, easing: ease }),
});

export const fundoEscuro = `radial-gradient(120% 80% at 50% 20%, #232323 0%, ${color.night} 70%)`;

/** Painel vertical 9:16 de altura cheia, encostado na direita (feed/h). */
export const usePainel = () => {
  const { width, height } = useVideoConfig();
  const w = Math.round((height * 9) / 16);
  return { w, h: height, x: width - w, colW: width - w };
};

/** Divide `texto` em [antes, alvo, depois] na 1ª ocorrência de `alvo` (para marca-texto). */
export const partir = (texto: string, alvo: string): [string, string, string] => {
  const i = texto.indexOf(alvo);
  if (i < 0) throw new Error(`destaque "${alvo}" não aparece no texto "${texto}"`);
  return [texto.slice(0, i), alvo, texto.slice(i + alvo.length)];
};
