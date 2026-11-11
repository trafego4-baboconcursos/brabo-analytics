import type React from "react";
import { Carimbo } from "./Carimbo";
import { Cartao } from "./Cartao";
import { Checklist } from "./Checklist";
import { Contador } from "./Contador";
import { Cta } from "./Cta";
import { Desenho } from "./Desenho";
import { Grafico } from "./Grafico";
import { Manchete } from "./Manchete";
import { PapelMesa } from "./PapelMesa";
import { Rota } from "./Rota";
import { Splash } from "./Splash";
import type { NomeCena, PropsCena } from "./tipos";

/**
 * Biblioteca de cenas. Os nomes também estão em nomes.json, que o validador
 * em Python (scripts/video/criativo_schema.py) lê — manter os dois iguais
 * (o teste tests/test_video_criativo.py confere).
 */
export const CENAS: { [N in NomeCena]: React.FC<PropsCena<N>> } = {
  Desenho,
  Manchete,
  Grafico,
  Carimbo,
  Rota,
  PapelMesa,
  Cartao,
  Checklist,
  Contador,
  Splash,
  Cta,
};

export type { NomeCena, PropsCena, PropsPorCena } from "./tipos";
