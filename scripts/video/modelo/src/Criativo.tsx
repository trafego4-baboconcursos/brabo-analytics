import React from "react";
import { Audio, Video } from "@remotion/media";
import type { Caption } from "@remotion/captions";
import { AbsoluteFill, Composition, Sequence, staticFile, useVideoConfig } from "remotion";
import { Captions } from "./Captions";
import { CENAS } from "./cenas";
import { EmendaContext } from "./Cutaway";
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

export const Criativo: React.FC<{ formato: ChaveFormato }> = ({ formato }) => {
  const { fps } = useVideoConfig();
  const f = criativo.formatos[formato]!;
  const cenas = criativo.cenas;
  return (
    <AbsoluteFill style={{ background: "black" }}>
      <Video name={`Bruto ${criativo.codigo} (${f.video})`} src={staticFile(f.video)} style={{ width: "100%", height: "100%" }} />
      {cenas.map((c) => {
        const Cena = CENAS[c.componente] as React.FC<{ start: number; dur: number; props: unknown }>;
        const dur = Math.round((c.ate - c.de) * fps);
        // colada na anterior/próxima (diferença < 1 quadro) = corte seco entre as duas
        const emenda = {
          entrada: cenas.some((o) => o !== c && Math.abs(o.ate - c.de) < 1 / fps),
          saida: cenas.some((o) => o !== c && Math.abs(o.de - c.ate) < 1 / fps),
        };
        return (
          <Sequence key={c.id} name={`${c.id} · ${c.componente}`} from={Math.round(c.de * fps)} durationInFrames={dur}>
            <EmendaContext.Provider value={emenda}>
              <Cena start={c.de} dur={dur} props={c.props} />
            </EmendaContext.Provider>
          </Sequence>
        );
      })}
      <Captions captions={captions} cfg={{
        cobertos: criativo.cobertos,
        cta: criativo.cta,
        seloBrutoAte: criativo.selo_bruto_ate_s ?? null,
        queimadaDesde: f.legenda_queimada ? (f.queimada_desde_s ?? 0) : null,
      }} />
      <Efeitos ganho={f.ganho_sfx} />
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
