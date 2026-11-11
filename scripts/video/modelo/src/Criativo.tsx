import React from "react";
import { Audio, Video } from "@remotion/media";
import type { Caption } from "@remotion/captions";
import { AbsoluteFill, Composition, Sequence, staticFile, useVideoConfig } from "remotion";
import { Captions } from "./Captions";
import { CENAS } from "./cenas";
import { EmendaContext } from "./Cutaway";
import { FUNDO, LEGENDA, PecasContext, type Ajuste } from "./pecas";
import captionsJson from "./data/captions.json";
import criativoJson from "./data/criativo.resolvido.json";

/*
 * Composição genérica: monta o criativo a partir de src/data/criativo.resolvido.json,
 * gerado por `python -m scripts.video.criativo_schema` a partir do criativo.json.
 * Um bruto por formato (mesma montagem e mesmo áudio); as cenas escolhem o layout
 * pelo tamanho da composição (theme.ts → useFormato).
 */

type ChaveFormato = "story" | "feed" | "h";
type Formato = {
  video: string;
  legenda_queimada: boolean;
  queimada_desde_s?: number;
  ganho_sfx: number;
};
type Cena = {
  id: string;
  componente: keyof typeof CENAS;
  de: number;
  ate: number;
  props: unknown;
  sfx: [number, string, number][];
  ajustes?: Partial<Record<ChaveFormato, Record<string, Ajuste>>>;
};
type Resolvido = {
  codigo: string;
  duracao_s: number;
  selo_bruto_ate_s?: number;
  formatos: Partial<Record<ChaveFormato, Formato>>;
  cenas: Cena[];
  cobertos: [number, number][];
  cta: [number, number] | null;
};

const criativo = criativoJson as unknown as Resolvido;
const captions = captionsJson as Caption[];

const TAMANHO: Record<ChaveFormato, { id: string; width: number; height: number }> = {
  story: { id: "Criativo-Story", width: 1080, height: 1920 },
  feed: { id: "Criativo-Feed", width: 1080, height: 1080 },
  h: { id: "Criativo-Horizontal", width: 1920, height: 1080 },
};

const Efeitos: React.FC<{ ganho: number }> = ({ ganho }) => {
  const { fps } = useVideoConfig();
  return (
    <>
      {criativo.cenas.flatMap((c) =>
        c.sfx.map(([at, nome, vol]) => (
          <Sequence key={`${c.id}-${at}-${nome}`} name={`SFX ${nome} @${at}s`} from={Math.round(at * fps)}
            durationInFrames={2 * fps} layout="none">
            <Audio src={staticFile(`sfx/${nome}.wav`)} volume={Math.min(1, vol * ganho)} />
          </Sequence>
        )),
      )}
    </>
  );
};

/**
 * `soCena` + `isolar`: render de camadas do storyboard (render-pecas.mjs). Só a cena pedida;
 * isolar = id de uma peça → só ela, com fundo transparente; isolar = FUNDO → bruto + cena sem as
 * peças e sem legenda; isolar = LEGENDA → só a legenda (camada de cima, como no vídeo).
 */
export const Criativo: React.FC<{ formato: ChaveFormato; soCena?: string; isolar?: string }> = ({ formato, soCena, isolar }) => {
  const { fps } = useVideoConfig();
  const f = criativo.formatos[formato]!;
  const cenas = soCena ? criativo.cenas.filter((c) => c.id === soCena) : criativo.cenas;
  const peca = isolar !== undefined && isolar !== FUNDO;
  return (
    <AbsoluteFill style={{ background: peca ? "transparent" : "black" }}>
      {!peca && <Video name={`Bruto ${criativo.codigo} (${f.video})`} src={staticFile(f.video)} style={{ width: "100%", height: "100%" }} />}
      {cenas.map((c) => {
        const Cena = CENAS[c.componente] as React.FC<{ start: number; dur: number; props: unknown }>;
        const dur = Math.round((c.ate - c.de) * fps);
        // colada na anterior/próxima (diferença < 1 quadro) = corte seco entre as duas
        const emenda = {
          entrada: criativo.cenas.some((o) => o !== c && Math.abs(o.ate - c.de) < 1 / fps),
          saida: criativo.cenas.some((o) => o !== c && Math.abs(o.de - c.ate) < 1 / fps),
        };
        const pecas = { ajustes: c.ajustes?.[formato] ?? {}, isolar: isolar ?? null };
        return (
          <Sequence key={c.id} name={`${c.id} · ${c.componente}`} from={Math.round(c.de * fps)} durationInFrames={dur}>
            <EmendaContext.Provider value={emenda}>
              <PecasContext.Provider value={pecas}>
                <Cena start={c.de} dur={dur} props={c.props} />
              </PecasContext.Provider>
            </EmendaContext.Provider>
          </Sequence>
        );
      })}
      {(isolar === undefined || isolar === LEGENDA) && <Captions captions={captions} cfg={{
        cobertos: criativo.cobertos,
        cta: criativo.cta,
        seloBrutoAte: criativo.selo_bruto_ate_s ?? null,
        queimadaDesde: f.legenda_queimada ? (f.queimada_desde_s ?? 0) : null,
      }} />}
      {!soCena && <Efeitos ganho={f.ganho_sfx} />}
    </AbsoluteFill>
  );
};

export const CriativoComposicoes: React.FC = () => (
  <>
    {(Object.keys(criativo.formatos) as ChaveFormato[]).map((k) => (
      <Composition key={k} id={TAMANHO[k].id} component={Criativo} durationInFrames={Math.round(criativo.duracao_s * 30)}
        fps={30} width={TAMANHO[k].width} height={TAMANHO[k].height} defaultProps={{ formato: k }} />
    ))}
  </>
);
