import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, raio, useAt, useFormato } from "../theme";
import { appear, fundoEscuro } from "./comum";
import type { PropsCena } from "./tipos";

/** Lista de itens que entram com check na palavra falada; h: grade 2×2. */
export const Checklist: React.FC<PropsCena<"Checklist">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const size = pick(f, { story: 48, feed: 40, h: 44 });
  return (
    <Cutaway durationInFrames={dur} background={fundoEscuro}>
      <div style={{
        position: "absolute", top: pick(f, { story: 220, feed: 60, h: 120 }),
        left: pick(f, { story: 90, feed: 90, h: 150 }), right: pick(f, { story: 90, feed: 90, h: 150 }), color: color.text,
      }}>
        <div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.muted }}>{props.kicker}</div>
        <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 84, feed: 66, h: 84 }), lineHeight: 1.05,
          margin: pick(f, { story: "16px 0 50px", feed: "12px 0 30px", h: "14px 0 44px" }) }}>
          {props.titulo}
        </div>
        <div style={{ display: f === "h" ? "grid" : "block", gridTemplateColumns: "1fr 1fr", columnGap: 28 }}>
          {props.itens.map((item, i) => {
            const destaque = props.destacarUltimo && i === props.itens.length - 1;
            const on = interpolate(frame, [t(item.em), t(item.em) + 8], [0, 1], clamp);
            return (
              <div key={item.texto} style={{
                display: "flex", alignItems: "center", gap: pick(f, { story: 30, feed: 24, h: 28 }),
                padding: pick(f, { story: "30px 34px", feed: "22px 28px", h: "30px 34px" }),
                marginBottom: pick(f, { story: 22, feed: 16, h: 24 }), borderRadius: 26,
                background: destaque ? color.coral : color.card, border: `2px solid ${destaque ? color.coral : color.line}`,
                fontFamily: font.ui, fontWeight: destaque ? 800 : 600, fontSize: size, ...appear(frame, t(item.em)),
              }}>
                <div style={{
                  width: size * 1.25, height: size * 1.25, flexShrink: 0, borderRadius: raio.pilula, display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: size * 0.75, background: destaque ? "white" : color.lime,
                  color: destaque ? color.coral : color.ink, scale: interpolate(on, [0, 1], [0.3, 1]),
                }}>✓</div>
                {item.texto}
              </div>
            );
          })}
        </div>
      </div>
    </Cutaway>
  );
};
