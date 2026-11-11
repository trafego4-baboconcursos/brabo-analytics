import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { color, font, pick, useAt, useFormato } from "../theme";
import { appear } from "./comum";
import type { PropsCena } from "./tipos";

/**
 * Botão de chamada por cima do vídeo (não cobre a pessoa). Embaixo no story;
 * no feed/h acima da faixa de legenda (inclusive da legenda queimada do bruto, y≈855–970).
 */
export const Cta: React.FC<PropsCena<"Cta">> = ({ start, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const bob = Math.sin(frame / 6) * 8;
  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div style={{
        position: "absolute", top: pick(f, { story: 1480, feed: 636, h: 600 }), padding: "26px 44px", borderRadius: 30,
        background: color.coral, color: "white", fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 56, feed: 50, h: 54 }),
        textAlign: "center", boxShadow: "0 20px 50px rgba(0,0,0,0.4)", ...appear(frame, 0),
      }}>
        {props.titulo}
        <div style={{ fontWeight: 600, fontSize: pick(f, { story: 38, feed: 34, h: 36 }), opacity: 0.9 }}>{props.subtitulo}</div>
      </div>
      <div style={{
        position: "absolute", top: pick(f, { story: 1680, feed: 790, h: 752 }), fontFamily: font.ui, fontWeight: 800,
        fontSize: pick(f, { story: 48, feed: 40, h: 42 }), color: "white",
        textShadow: "0 4px 20px rgba(0,0,0,0.6)", translate: `0px ${bob}px`, opacity: appear(frame, t(props.chamada.em)).opacity,
      }}>
        {props.chamada.texto}
      </div>
    </AbsoluteFill>
  );
};
