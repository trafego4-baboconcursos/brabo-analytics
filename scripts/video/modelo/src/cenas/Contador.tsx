import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, raio, useAt, useFormato } from "../theme";
import { appear, fundoEscuro } from "./comum";
import { Peca } from "../pecas";
import type { PropsCena } from "./tipos";

/** Número grande contando + rótulo + medalhas que estalam na fala. */
export const Contador: React.FC<PropsCena<"Contador">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const n = Math.round(interpolate(frame, [t(props.conta[0]), t(props.conta[1])], [0, props.numero], clamp));
  const m = props.medalhas;
  const medalha = pick(f, { story: 150, feed: 124, h: 150 });
  const medalhas = (
    <div style={{ display: "flex", alignItems: "center", gap: 26, ...appear(frame, t(m.em)) }}>
      {Array.from({ length: m.quantidade }).map((_, k) => (
        <div key={k} style={{
          width: medalha, height: medalha, borderRadius: raio.pilula, background: "#E9B949", color: color.ink, display: "flex",
          alignItems: "center", justifyContent: "center", fontFamily: font.ui, fontWeight: 800, fontSize: medalha * 0.43,
          boxShadow: "inset 0 -10px 0 rgba(0,0,0,0.18)",
          scale: interpolate(frame, [t(m.em) + k * 4, t(m.em) + k * 4 + 10], [0.4, 1], { ...clamp, easing: Easing.back(2) }),
        }}>{m.marca}</div>
      ))}
      <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 64, feed: 56, h: 64 }), whiteSpace: "pre-line" }}>
        {m.texto}
      </div>
    </div>
  );
  return (
    <Cutaway durationInFrames={dur} background={fundoEscuro}>
      <div style={{
        position: "absolute", top: pick(f, { story: 230, feed: 70, h: 190 }),
        left: pick(f, { story: 90, feed: 90, h: 170 }), right: pick(f, { story: 90, feed: 90, h: 170 }), color: color.text,
      }}>
        <Peca id="kicker"><div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.muted }}>{props.kicker}</div></Peca>
        {/* h: número + texto à esquerda, medalhas à direita na mesma linha */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: f === "h" ? "nowrap" : "wrap" }}>
          <Peca id="numero"><div style={{ display: "flex", alignItems: "baseline", gap: 30 }}>
            <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 380, feed: 300, h: 380 }), letterSpacing: -14, lineHeight: 1 }}>{n}</div>
            <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 72, feed: 62, h: 76 }), lineHeight: 1.05, whiteSpace: "pre-line" }}>
              {props.rotulo}
            </div>
          </div></Peca>
          <Peca id="medalhas" style={{ marginTop: f === "h" ? 0 : pick(f, { story: 40, feed: 24, h: 0 }), width: f === "h" ? "auto" : "100%" }}>{medalhas}</Peca>
        </div>
      </div>
    </Cutaway>
  );
};
