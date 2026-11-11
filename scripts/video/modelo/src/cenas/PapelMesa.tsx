import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, useAt, useFormato } from "../theme";
import { Handwriting, Kicker, Sheet } from "../inserts/Paper";
import { appear, ease } from "./comum";
import { Peca } from "../pecas";
import type { PropsCena } from "./tipos";

/**
 * Folha sobre a base de corte verde: curva "ruim" (cinza, plana) × curva "boa"
 * (subindo), círculo vermelho à mão no topo da boa, anotação e adesivo.
 * Gráfico desenhado em 780×420 e escalado por formato (mantém o círculo redondo).
 */
export const PapelMesa: React.FC<PropsCena<"PapelMesa">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const W = 780, H = 420;
  const k = pick(f, { story: 1, feed: 0.72, h: 0.84 });
  const ruim = "M 0 330 C 80 300, 140 340, 220 310 S 380 330, 460 300 S 640 320, 780 300";
  const boa = "M 0 340 C 160 320, 280 260, 420 190 S 660 60, 780 30";
  const draw = (a: number, b: number) => interpolate(frame, [t(a), t(b)], [1, 0], { ...clamp, easing: ease });
  const tape: React.CSSProperties = { position: "absolute", width: 170, height: 52, background: "rgba(235,225,200,0.75)" };
  const { curvaRuim, curvaBoa } = props;

  return (
    <Cutaway
      durationInFrames={dur}
      background={`repeating-linear-gradient(0deg, transparent 0 59px, rgba(255,255,255,0.12) 59px 61px),
        repeating-linear-gradient(90deg, transparent 0 59px, rgba(255,255,255,0.12) 59px 61px), ${color.mat}`}
    >
      <Sheet tilt={-2} width={pick(f, { story: 900, feed: 900, h: 1360 })} top={pick(f, { story: 210, feed: 40, h: 50 })}>
        <div style={{ ...tape, top: -26, left: pick(f, { story: 340, feed: 340, h: 500 }), rotate: "-4deg" }} />
        <Peca id="kicker"><Kicker>{props.kicker}</Kicker></Peca>
        <Peca id="titulo" style={{ marginBottom: pick(f, { story: 30, feed: 18, h: 24 }) }}><div style={{ fontFamily: font.serif, fontWeight: 700, fontSize: pick(f, { story: 64, feed: 52, h: 56 }), lineHeight: 1.1 }}>
          {props.titulo}
        </div></Peca>
        <Peca id="grafico"><svg width={W * k} height={H * k} viewBox={`0 0 ${W} ${H}`} style={{ overflow: "visible", display: "block",
          marginLeft: f === "h" ? 220 : 0 }}>
          <line x1={0} y1={H} x2={W} y2={H} stroke={color.ink} strokeWidth={3} />
          <line x1={0} y1={0} x2={0} y2={H} stroke={color.ink} strokeWidth={3} />
          <path d={ruim} fill="none" stroke="#9A948A" strokeWidth={7} pathLength={1} strokeDasharray={1}
            strokeDashoffset={draw(curvaRuim.em[0], curvaRuim.em[1])} />
          <path d={boa} fill="none" stroke={color.ink} strokeWidth={8} pathLength={1} strokeDasharray={1}
            strokeDashoffset={draw(curvaBoa.em[0], curvaBoa.em[1])} />
          <text x={W} y={360} textAnchor="end" fontFamily={font.mono} fontSize={26 / Math.min(k, 1)} fill="#7A746A"
            opacity={interpolate(frame, [t(curvaRuim.em[0] + 0.8), t(curvaRuim.em[0] + 1.2)], [0, 1], clamp)}>{curvaRuim.rotulo}</text>
          <text x={430} y={150} fontFamily={font.mono} fontSize={26 / Math.min(k, 1)} fill={color.ink}
            opacity={interpolate(frame, [t(curvaBoa.em[0] + 0.4), t(curvaBoa.em[0] + 0.8)], [0, 1], clamp)}>{curvaBoa.rotulo}</text>
          {/* círculo vermelho feito à mão em volta do topo da curva */}
          <path d="M 700 -10 C 790 -40, 860 30, 800 80 C 740 120, 640 80, 660 20 C 670 -10, 720 -30, 760 -25"
            fill="none" stroke={color.marker} strokeWidth={7} strokeLinecap="round" pathLength={1}
            opacity={frame >= t(props.circulo.em) ? 1 : 0}
            strokeDasharray={1} strokeDashoffset={draw(props.circulo.em, props.circulo.em + 0.6)} />
        </svg></Peca>
        <Peca id="mao"><Handwriting from={t(props.mao.em)} style={{ textAlign: "right", marginTop: 10, fontSize: pick(f, { story: 64, feed: 52, h: 60 }),
          paddingLeft: pick(f, { story: 300, feed: 240, h: 0 }) }}>
          {props.mao.texto}
        </Handwriting></Peca>
      </Sheet>
      <Peca id="adesivo" style={{ position: "absolute", top: pick(f, { story: 1010, feed: 610, h: 600 }), left: pick(f, { story: 70, feed: 24, h: 40 }) }}>
      <div
        style={{
          position: "relative",
          rotate: "-6deg", background: "var(--cor, #F7F3EA)", padding: "10px 26px",
          fontFamily: font.stamp, fontSize: pick(f, { story: 88, feed: 70, h: 84 }), color: `var(--cor-texto, ${color.ink})`,
          boxShadow: "0 12px 30px rgba(0,0,0,0.35)", ...appear(frame, t(props.adesivo.em)),
        }}
      >
        <div style={{ ...tape, top: -22, left: 20, width: 110, rotate: "8deg" }} />
        {props.adesivo.texto}
      </div>
      </Peca>
    </Cutaway>
  );
};
