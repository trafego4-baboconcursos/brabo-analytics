import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Cutaway } from "../Cutaway";
import { color, font, pick, raio, useAt, useFormato } from "../theme";
import { Stamp } from "../inserts/Paper";
import { appear, fundoEscuro } from "./comum";
import type { PropsCena } from "./tipos";

/** Cartão escuro com nome grande (curso, produto) + subtítulo + carimbo lima. */
export const Cartao: React.FC<PropsCena<"Cartao">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const { width } = useVideoConfig();
  const cardW = pick(f, { story: 900, feed: 900, h: 1360 });
  // "\n" do título quebra a linha no story/feed; no horizontal o nome cabe numa linha
  const titulo = f === "h" ? props.titulo.replace(/\n/g, " ") : props.titulo;
  return (
    <Cutaway durationInFrames={dur} background={fundoEscuro}>
      <div style={{
        position: "absolute", top: pick(f, { story: 300, feed: 110, h: 170 }), left: (width - cardW) / 2, width: cardW,
        padding: pick(f, { story: 64, feed: 56, h: 72 }), borderRadius: raio.cartao, background: color.card,
        border: `2px solid ${color.line}`, color: color.text, boxSizing: "border-box",
      }}>
        <div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.coral }}>{props.kicker}</div>
        <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 150, feed: 130, h: 170 }), letterSpacing: -5,
          lineHeight: 1, marginTop: 24, whiteSpace: "pre-line" }}>
          {titulo}
        </div>
        <div style={{ fontFamily: font.ui, fontSize: pick(f, { story: 46, feed: 42, h: 50 }), color: color.muted, marginTop: 26,
          maxWidth: f === "h" ? cardW - 2 * 72 - 440 : "none", ...appear(frame, t(props.subtitulo.em)) }}>
          {props.subtitulo.texto}
        </div>
        <div style={{ position: "absolute", right: 60, top: pick(f, { story: 200, feed: 170, h: 250 }) }}>
          <Stamp from={t(props.carimbo.em)} rotate={-12} style={{ color: color.lime, borderColor: color.lime, mixBlendMode: "normal",
            fontSize: pick(f, { story: 92, feed: 80, h: 96 }) }}>
            {props.carimbo.texto}
          </Stamp>
        </div>
      </div>
    </Cutaway>
  );
};
