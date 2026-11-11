import React, { useMemo } from "react";
import { Caption, createTikTokStyleCaptions, TikTokPage } from "@remotion/captions";
import { AbsoluteFill, interpolate, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, color, font, pick, useFormato } from "./theme";

/**
 * O bruto já traz a caixa "CONCURSO PÚBLICO R$ 7.234,00" (y≈1170–1470) nos
 * primeiros ~6,8 s. Nesse trecho a legenda sobe para o vão entre o queixo e a caixa.
 */
const CAIXA_DO_BRUTO_ATE_MS = 6800;
// de 3,4 s em diante o desenho da dona de casa cobre a caixa: legenda volta ao lugar
const DESENHO_DESDE_MS = 3400;
// posições por formato (story 1080×1920 · feed 1080×1080 · h 1920×1080)
// feed: caixa do bruto em y≈635–890, queixo dela ≈515 · h: caixa em y≈720–975, queixo ≈600
const TOPO_PADRAO = { story: 1330, feed: 838, h: 878 };
const TOPO_ACIMA_DA_CAIXA = { story: 990, feed: 500, h: 585 };
// no fim o botão "Cadastro gratuito" ocupa a parte de baixo (y≈1480–1750): legenda sobe
const CTA_DESDE_MS = 133000;
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
// a legenda queimada só começa no 1º corte (≈7,1 s); antes disso (abertura com ela)
// a nossa entra no lugar, acima da caixa "CONCURSO PÚBLICO" (feed topo y≈635, h y≈720)
const BRUTO_SEM_LEGENDA_ATE_S = 7.1;
const BOTTOM_ACIMA_DA_CAIXA = { feed: 470, h: 380 };

const CaptionPage: React.FC<{ page: TikTokPage; cobertos: [number, number][] }> = ({ page, cobertos }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const nowMs = page.startMs + (frame / fps) * 1000;
  const f = useFormato();

  if (f !== "story") {
    // só enquanto a animação cobre o vídeo (folga de 0,15 s nas bordas por causa do fade)
    const s = nowMs / 1000;
    const abertura = s < BRUTO_SEM_LEGENDA_ATE_S;
    if (!abertura && !cobertos.some(([de, ate]) => s >= de + 0.15 && s < ate - 0.15)) return null;
    const e = ESTILO_BRUTO[f];
    // antes do desenho a caixa do bruto está na tela: legenda acima dela
    const bottom = nowMs < DESENHO_DESDE_MS ? BOTTOM_ACIMA_DA_CAIXA[f] : e.bottom;
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
            nowMs < DESENHO_DESDE_MS && nowMs < CAIXA_DO_BRUTO_ATE_MS
              ? TOPO_ACIMA_DA_CAIXA
              : nowMs >= CTA_DESDE_MS
                ? TOPO_ACIMA_DO_CTA
                : TOPO_PADRAO,
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

export const Captions: React.FC<{ captions: Caption[]; cobertos: [number, number][] }> = ({ captions, cobertos }) => {
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
            <CaptionPage page={page} cobertos={cobertos} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
