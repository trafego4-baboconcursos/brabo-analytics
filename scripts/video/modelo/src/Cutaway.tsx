import React, { createContext, useContext } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { clamp } from "./theme";
import { useIsolandoPeca } from "./pecas";

/**
 * Emenda entre inserts colados (um termina no quadro em que o outro começa).
 * Nesses lados o fundo não faz fade, senão o vídeo do Mateus aparece por
 * alguns quadros entre um e outro. Preenchido pela composição.
 */
export const EmendaContext = createContext<{ entrada: boolean; saida: boolean }>({
  entrada: false,
  saida: false,
});

/**
 * Moldura de todo insert de tela cheia: o fundo entra rápido, o conteúdo sobe
 * com um leve zoom (como os cards da referência) e tudo sai num fade curto.
 */
export const Cutaway: React.FC<{
  durationInFrames: number;
  background: string;
  children: React.ReactNode;
}> = ({ durationInFrames, background, children }) => {
  const frame = useCurrentFrame();
  const emenda = useContext(EmendaContext);
  const ease = Easing.bezier(0.16, 1, 0.3, 1);
  const d = durationInFrames;
  const isolando = useIsolandoPeca();

  return (
    <AbsoluteFill
      style={{
        background: isolando ? "transparent" : background,
        visibility: isolando ? "hidden" : undefined,
        opacity: interpolate(frame, [0, 5, d - 6, d], [emenda.entrada ? 1 : 0, 1, 1, emenda.saida ? 1 : 0], clamp),
      }}
    >
      <AbsoluteFill
        style={{
          // no lado emendado o conteúdo ainda some/entra, mas sobre o fundo opaco
          opacity: interpolate(frame, [0, 5, d - 6, d], [emenda.entrada ? 0 : 1, 1, 1, emenda.saida ? 0 : 1], clamp),
          scale: interpolate(frame, [0, 14, d], [0.9, 1, 1.04], { ...clamp, easing: ease }),
          translate: interpolate(frame, [0, 14], ["0px 60px", "0px 0px"], { ...clamp, easing: ease }),
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
