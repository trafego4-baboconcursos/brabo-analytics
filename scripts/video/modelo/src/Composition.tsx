import { Audio, Video } from "@remotion/media";
import type { Caption } from "@remotion/captions";
import { AbsoluteFill, Composition, Sequence, staticFile, useVideoConfig } from "remotion";
import { Captions } from "./Captions";
import { EmendaContext } from "./Cutaway";
import captionsJson from "./data/captions.json";
import {
  Aprovacoes,
  CargoManchete,
  ChecklistCurso,
  CtaFinal,
  DonaDeCasa,
  SemFaculdade,
  TemFilho,
  MetodoMesa,
  ProjetoCard,
  RotaMapa,
  SalarioGrafico,
  StatusCarimbo,
} from "./inserts/Inserts";

const captions = captionsJson as Caption[];
const DURACAO_S = 146.4;

/**
 * Inserts de tela cheia, em segundos do bruto (iguais à transcrição).
 * O áudio do bruto segue por baixo: só a imagem é coberta.
 */
// Fins/inícios alinhados aos cortes de câmera do bruto (+0,2 s do fade), para não
// sobrar uma tomada de poucos quadros entre a animação e o próximo corte.
// Conferir com: python checar_cortes.py
const INSERTS = [
  { nome: "0 Desenho · dona de casa", C: DonaDeCasa, de: 3.4, ate: 9.0 },
  { nome: "0b Desenho · sem faculdade", C: SemFaculdade, de: 19.13, ate: 22.4 },
  { nome: "0c Desenho · tem filho", C: TemFilho, de: 52.7, ate: 57.1 },
  { nome: "1 Manchete · cargo", C: CargoManchete, de: 27.9, ate: 33.2 },
  { nome: "2 Gráfico · salário", C: SalarioGrafico, de: 33.2, ate: 42.8 },
  { nome: "3 Carimbo · status", C: StatusCarimbo, de: 42.8, ate: 51.6 },
  { nome: "4 Rota · 2h por dia", C: RotaMapa, de: 62.9, ate: 75.8 },
  { nome: "5 Papel na mesa · método", C: MetodoMesa, de: 85.8, ate: 93.4 },
  { nome: "6 Cartão · Projeto INSS", C: ProjetoCard, de: 100.8, ate: 105.4 },
  { nome: "7 Checklist · o que aprende", C: ChecklistCurso, de: 110.7, ate: 118.3 },
  { nome: "8 Contador · aprovações", C: Aprovacoes, de: 120.3, ate: 124.1 },
  { nome: "CTA", C: CtaFinal, de: 133.0, ate: DURACAO_S },
];

/**
 * Efeitos sonoros (public/sfx, baixados de remotion.media). Volume baixo:
 * os .wav têm pico em -3 dB e a fala média em -18,7 dB.
 */
type Sfx = "whoosh" | "whip" | "page-turn" | "switch" | "mouse-click" | "ding" | "vine-boom";
const SFX: [number, Sfx, number][] = [
  // 0 desenho da dona de casa
  [3.4, "whoosh", 0.35], [4.4, "mouse-click", 0.3], [4.82, "mouse-click", 0.3], [6.25, "mouse-click", 0.3],
  // 0b sem faculdade / 0c tem filho
  [19.13, "whoosh", 0.35], [19.66, "mouse-click", 0.3], [20.8, "mouse-click", 0.3],
  [52.7, "whoosh", 0.35], [53.82, "mouse-click", 0.3], [54.28, "mouse-click", 0.3], [55.12, "mouse-click", 0.3],
  // 1 manchete
  [27.9, "page-turn", 0.45], [32.4, "switch", 0.2],
  // 2 salário
  [33.2, "whoosh", 0.35], [35.5, "ding", 0.22], [38.5, "ding", 0.22], [40.9, "mouse-click", 0.3],
  // 3 carimbo
  [42.8, "page-turn", 0.45], [46.1, "vine-boom", 0.2], [47.4, "switch", 0.2],
  // 4 mapa + montanha
  [62.9, "whoosh", 0.35], [70.3, "mouse-click", 0.3], [73.75, "ding", 0.3],
  // 5 papel na mesa
  [85.8, "page-turn", 0.45], [89.5, "whip", 0.3], [91.7, "switch", 0.2],
  // 6 Projeto INSS
  [100.8, "whoosh", 0.35], [103.3, "vine-boom", 0.2],
  // 7 checklist
  [110.7, "whoosh", 0.35], [110.9, "mouse-click", 0.35], [112.0, "mouse-click", 0.35],
  [114.5, "mouse-click", 0.35], [117.1, "mouse-click", 0.35],
  // 8 aprovações
  [120.3, "whoosh", 0.35], [121.2, "ding", 0.28], [122.3, "switch", 0.25],
  // CTA
  [133.0, "whoosh", 0.3], [135.6, "ding", 0.2],
];

const SoundEffects: React.FC<{ ganho: number }> = ({ ganho }) => {
  const { fps } = useVideoConfig();
  return (
    <>
      {SFX.map(([at, nome, vol]) => (
        <Sequence key={`${at}-${nome}`} name={`SFX ${nome} @${at}s`} from={Math.round(at * fps)} durationInFrames={2 * fps} layout="none">
          <Audio src={staticFile(`sfx/${nome}.wav`)} volume={Math.min(1, vol * ganho)} />
        </Sequence>
      ))}
    </>
  );
};

type Props = { video: string; ganhoSfx: number };

export const Ad358: React.FC<Props> = ({ video, ganhoSfx }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: "black" }}>
      <Video name={`Bruto AD358 (${video})`} src={staticFile(video)} style={{ width: "100%", height: "100%" }} />
      {INSERTS.map(({ nome, C, de, ate }) => {
        const dur = Math.round((ate - de) * fps);
        // colado no anterior/próximo (diferença < 1 quadro) = corte seco entre os dois
        const emenda = {
          entrada: INSERTS.some((o) => Math.abs(o.ate - de) < 1 / fps),
          saida: INSERTS.some((o) => Math.abs(o.de - ate) < 1 / fps),
        };
        return (
          <Sequence key={nome} name={nome} from={Math.round(de * fps)} durationInFrames={dur}>
            <EmendaContext.Provider value={emenda}>
              <C start={de} dur={dur} />
            </EmendaContext.Provider>
          </Sequence>
        );
      })}
      {/* trechos em que uma animação cobre o vídeo (o CTA não cobre): no feed/h a nossa
          legenda só aparece neles, porque o bruto já traz legenda queimada */}
      <Captions captions={captions} cobertos={INSERTS.filter((i) => i.nome !== "CTA").map((i) => [i.de, i.ate])} />
      <SoundEffects ganho={ganhoSfx} />
    </AbsoluteFill>
  );
};

/**
 * Um bruto por formato (mesma montagem e mesmo áudio). O horizontal vem ~5 dB
 * mais alto (rms 1,77×), então os efeitos sobem na mesma proporção.
 * As cenas escolhem o layout pelo tamanho da composição (theme.ts → useFormato).
 */
export const MyComposition = () => (
  <>
    <Composition id="AD358-Referencia" component={Ad358} durationInFrames={Math.round(DURACAO_S * 30)}
      fps={30} width={1080} height={1920} defaultProps={{ video: "ad358-story.mp4", ganhoSfx: 1 }} />
    <Composition id="AD358-Feed" component={Ad358} durationInFrames={Math.round(DURACAO_S * 30)}
      fps={30} width={1080} height={1080} defaultProps={{ video: "ad358-feed.mp4", ganhoSfx: 1 }} />
    <Composition id="AD358-Horizontal" component={Ad358} durationInFrames={Math.round(DURACAO_S * 30)}
      fps={30} width={1920} height={1080} defaultProps={{ video: "ad358-h.mp4", ganhoSfx: 1.77 }} />
  </>
);
