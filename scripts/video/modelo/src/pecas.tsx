import React, { createContext, useContext } from "react";

/*
 * Peças: os elementos de uma cena que o usuário pode mover/girar/redimensionar no Figma.
 * O layout padrão continua no código da cena; o criativo.json guarda só o AJUSTE de cada
 * peça por formato (cenas[].ajustes[formato][id]). O id é o caminho da prop ("titulo",
 * "etiquetas[0]") ou um nome fixo para o que não é texto ("folha", "grafico").
 */

export type Ajuste = { dx?: number; dy?: number; rot?: number; escala?: number };

/** `isolar`: render de camadas para o storyboard — o id da peça que fica visível sozinha, ou
 * FUNDO (tudo menos as peças). Sem `isolar`, render normal. */
export const FUNDO = "__fundo__";
export const PecasContext = createContext<{ ajustes: Record<string, Ajuste>; isolar: string | null }>({
  ajustes: {},
  isolar: null,
});

/** Render de uma peça isolada: o resto da cena (fundo, outras peças) fica transparente. */
export const useIsolandoPeca = () => {
  const { isolar } = useContext(PecasContext);
  return isolar !== null && isolar !== FUNDO;
};

/**
 * Embrulha um elemento da cena. `style` recebe o POSICIONAMENTO do elemento (position, top,
 * left, width, flex…), para a caixa da peça ser a caixa do elemento: girar e escalar são em
 * volta do centro dela. O ajuste usa translate/rotate/scale da própria peça, que somam às
 * animações do elemento de dentro.
 */
export const Peca: React.FC<{ id: string; style?: React.CSSProperties; children: React.ReactNode }> = ({ id, style, children }) => {
  const { ajustes, isolar } = useContext(PecasContext);
  const a = ajustes[id];
  return (
    <div
      data-peca={id}
      style={{
        ...style,
        ...(a ? { translate: `${a.dx ?? 0}px ${a.dy ?? 0}px`, rotate: `${a.rot ?? 0}deg`, scale: `${a.escala ?? 1}` } : {}),
        ...(isolar === null ? {} : { visibility: isolar === id ? "visible" : "hidden" }),
      }}
    >
      {children}
    </div>
  );
};
