import React, { useMemo } from "react";
import { Caption, createTikTokStyleCaptions, TikTokPage } from "@remotion/captions";
import { AbsoluteFill, interpolate, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, color, font, pick, useFormato } from "./theme";

/**
 * Quando a legenda muda de lugar (tudo vem do criativo.resolvido.json):
 * - `seloBrutoAte`: o bruto traz um selo próprio na faixa da legenda (no AD368, a caixa
 *   "CONCURSO PÚBLICO" até 6,8 s); enquanto ele está na tela e nenhuma cena cobre o
 *   vídeo, a legenda sobe para acima dele;
 * - `cta`: enquanto o botão final está na tela, a legenda sobe para acima dele;
 * - `queimadaDesde`: o bruto deste formato já tem legenda queimada a partir desse
 *   segundo — então a nossa só aparece antes disso ou quando uma cena cobre o vídeo,
 *   no estilo da do bruto.
 * As POSIÇÕES por formato ficam aqui (story 1080×1920 · feed 1080×1080 · h 1920×1080).
 */
export type ConfigLegenda = {
  cobertos: [number, number][];
  cta: [number, number] | null;
  seloBrutoAte: number | null;
  queimadaDesde: number | null;
};
const TOPO_PADRAO = { story: 1330, feed: 838, h: 878 };
const TOPO_ACIMA_DA_CAIXA = { story: 990, feed: 500, h: 585 };
const TOPO_ACIMA_DO_CTA = { story: 1176, feed: 668, h: 652 };
const FIM_DE_FRASE = /[.?!]\s*$/;

/**
 * Contorno redondo. O -webkit-text-stroke só faz junção em "miter" e solta
 * espinhos nos ângulos agudos (M, V, A, N). Aqui o contorno são 32 sombras
 * em círculo de raio R + uma sombra suave embaixo.
 */
const R = 7;
const CONTORNO = [
  ...Array.from({ length: 32 }, (_, i) => {
    const a = (i / 32) * Math.PI * 2;
    return `${(Math.cos(a) * R).toFixed(2)}px ${(Math.sin(a) * R).toFixed(2)}px 0 #000`;
  }),
  "0 6px 18px rgba(0,0,0,0.55)",
].join(", ");

/**
 * Feed e horizontal: o bruto JÁ TEM legenda queimada (branca, caixa alta, sombra
 * deslocada). Nesses formatos a nossa só aparece enquanto uma animação cobre o
 * vídeo, imitando a do bruto (medida em 11/11: feed maiúscula ≈36 px, linhas a 58 px,
 * última linha termina em y≈966; h ≈39 px, 62 px, y≈960) — a troca não aparece.
 */
const ESTILO_BRUTO = {
  feed: { fontSize: 50, lineHeight: "58px", bottom: 104, width: 980 },
  h: { fontSize: 54, lineHeight: "62px", bottom: 105, width: 1500 },
};
const SOMBRA_BRUTO = "3px 3px 0 rgba(0,0,0,0.92), 1px 1px 6px rgba(0,0,0,0.5)";
// estilo do bruto acima do selo dele (feed: selo y≈635–890 · h: y≈720–975)
const BOTTOM_ACIMA_DA_CAIXA = { story: 930, feed: 470, h: 380 };

const CaptionPage: React.FC<{ page: TikTokPage; cfg: ConfigLegenda }> = ({ page, cfg }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const nowMs = page.startMs + (frame / fps) * 1000;
  const f = useFormato();
  const s = nowMs / 1000;
  const coberto = cfg.cobertos.some(([de, ate]) => s >= de && s < ate);
  const sobreSelo = cfg.seloBrutoAte !== null && s < cfg.seloBrutoAte && !coberto;

  if (cfg.queimadaDesde !== null) {
    // só antes da legenda do bruto começar ou enquanto uma cena cobre o vídeo
    // (folga de 0,15 s nas bordas por causa do fade)
    const antes = s < cfg.queimadaDesde;
    if (!antes && !cfg.cobertos.some(([de, ate]) => s >= de + 0.15 && s < ate - 0.15)) return null;
    const e = ESTILO_BRUTO[f === "story" ? "feed" : f];
    const bottom = sobreSelo ? BOTTOM_ACIMA_DA_CAIXA[f] : e.bottom;
    return (
      <AbsoluteFill style={{ alignItems: "center" }}>
        <div style={{
          position: "absolute", bottom, width: e.width, textAlign: "center", fontFamily: font.caption,
          fontWeight: 800, fontSize: e.fontSize, lineHeight: e.lineHeight, textTransform: "uppercase",
          color: "white", textShadow: SOMBRA_BRUTO,
        }}>
          {page.tokens.map((t, i) => (
            <span key={t.fromMs} style={{ whiteSpace: "pre-wrap" }}>{i === 0 ? t.text.trimStart() : t.text}</span>
          ))}
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          // decide pelo instante atual, não pelo início da frase: uma frase que
          // começa antes do desenho desce junto com o corte para o desenho
          top: pick(
            f,
            sobreSelo ? TOPO_ACIMA_DA_CAIXA : cfg.cta && s >= cfg.cta[0] ? TOPO_ACIMA_DO_CTA : TOPO_PADRAO,
          ),
          width: pick(f, { story: 920, feed: 960, h: 1500 }),
          textAlign: "center",
          fontFamily: font.caption,
          fontWeight: 800,
          fontSize: pick(f, { story: 70, feed: 56, h: 62 }),
          lineHeight: 1.15,
          textTransform: "uppercase",
          color: "white",
          textShadow: CONTORNO,
          scale: interpolate(frame, [0, 4], [0.92, 1], clamp),
        }}
      >
        {page.tokens.map((t, i) => {
          const active = t.fromMs <= nowMs && t.toMs > nowMs;
          // frase nova (depois de ". ? !") começa na linha de baixo
          const novaFrase = i > 0 && FIM_DE_FRASE.test(page.tokens[i - 1].text);
          return (
            <React.Fragment key={t.fromMs}>
              {novaFrase && <br />}
              <span
                style={{
                  whiteSpace: "pre-wrap",
                  color: active ? color.lime : "white",
                }}
              >
                {novaFrase ? t.text.trimStart() : t.text}
              </span>
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Captions: React.FC<{ captions: Caption[]; cfg: ConfigLegenda }> = ({ captions, cfg }) => {
  const { fps } = useVideoConfig();
  const { pages } = useMemo(
    () =>
      createTikTokStyleCaptions({
        captions,
        combineTokensWithinMilliseconds: 750,
        breakOnSilenceAfterMilliseconds: 400,
      }),
    [captions],
  );

  return (
    <AbsoluteFill name="Legendas">
      {pages.map((page, i) => {
        const next = pages[i + 1];
        const endMs = Math.min(
          next ? next.startMs : Infinity,
          page.startMs + page.durationMs + 300,
        );
        const from = Math.round((page.startMs / 1000) * fps);
        const dur = Math.max(1, Math.round(((endMs - page.startMs) / 1000) * fps));
        return (
          <Sequence key={page.startMs} from={from} durationInFrames={dur} layout="none">
            <CaptionPage page={page} cfg={cfg} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
