import React from "react";
import { AbsoluteFill, Composition, Sequence, useVideoConfig } from "remotion";
import { CATALOGO, DUR_CATALOGO } from "./catalogo-props";
import { CENAS, type NomeCena } from "./cenas";

/*
 * Catálogo de verificação: todas as cenas em sequência, cada uma com o texto
 * mais longo esperado (catalogo-props.ts). Para revisar: stills em
 * i*DUR_CATALOGO + (DUR_CATALOGO - 0,1) s, um por cena, em cada formato.
 * Dentro de cada Sequence o frame é relativo, então a cena recebe start=0 e
 * os tempos das props são relativos ao início dela.
 */
export const ORDEM: NomeCena[] = Object.keys(CENAS) as NomeCena[];

const Catalogo: React.FC = () => {
  const { fps } = useVideoConfig();
  const d = DUR_CATALOGO * fps;
  return (
    <AbsoluteFill style={{ background: "#3A3A3A" }}>
      {ORDEM.map((nome, i) => {
        const Cena = CENAS[nome] as React.FC<{ start: number; dur: number; props: unknown }>;
        return (
          <Sequence key={nome} name={`Catálogo · ${nome}`} from={i * d} durationInFrames={d}>
            <Cena start={0} dur={d} props={CATALOGO[nome]} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const duracao = ORDEM.length * DUR_CATALOGO * 30;

export const CatalogoComposicoes: React.FC = () => (
  <>
    <Composition id="Catalogo-Story" component={Catalogo} durationInFrames={duracao} fps={30} width={1080} height={1920} />
    <Composition id="Catalogo-Feed" component={Catalogo} durationInFrames={duracao} fps={30} width={1080} height={1080} />
    <Composition id="Catalogo-Horizontal" component={Catalogo} durationInFrames={duracao} fps={30} width={1920} height={1080} />
  </>
);
