import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, raio, useAt, useFormato } from "../theme";
import { appear, ease, fundoEscuro } from "./comum";
import { Peca } from "../pecas";
import type { PropsCena } from "./tipos";

/**
 * Número grande contando + curva em degraus se desenhando + rótulo do fim + selo.
 * h: número à esquerda, gráfico à direita, selo centralizado embaixo.
 */
export const Grafico: React.FC<PropsCena<"Grafico">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const { em } = props;
  const valor = Math.round(interpolate(frame, [t(em.conta[0]), t(em.conta[1])], [0, props.valorFinal], { ...clamp, easing: ease }));
  const linha = interpolate(frame, [t(em.linha[0]), t(em.linha[1])], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const W = pick(f, { story: 880, feed: 880, h: 820 });
  const H = pick(f, { story: 440, feed: 290, h: 380 });
  const [min, max] = props.escala ?? [Math.min(...props.pontos) * 0.9, Math.max(...props.pontos) * 1.25];
  const pts = props.pontos;
  const d = pts
    .map((v, i) => `${i === 0 ? "M" : "L"} ${(i / (pts.length - 1)) * W} ${H - ((v - min) / (max - min)) * H}`)
    .join(" ");

  const kicker = (
    <Peca id="kicker"><div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.muted }}>{props.kicker}</div></Peca>
  );
  const numero = (
    <Peca id="numero"><div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 190, feed: 150, h: 210 }), letterSpacing: -6, lineHeight: 1.1 }}>
      <span style={{ fontSize: pick(f, { story: 96, feed: 76, h: 104 }), verticalAlign: "top", marginRight: 10 }}>{props.prefixo}</span>
      {valor.toLocaleString("pt-BR")}
    </div></Peca>
  );
  const grafico = (
    <Peca id="grafico" style={{ width: W }}><svg width={W} height={H + 60} style={{ overflow: "visible" }}>
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1={0} x2={W} y1={(i / 3) * H} y2={(i / 3) * H} stroke="rgba(242,239,233,0.32)"
          strokeWidth={2} strokeDasharray="8 10" />
      ))}
      <line x1={0} y1={0} x2={0} y2={H} stroke="rgba(242,239,233,0.5)" strokeWidth={3} />
      <line x1={0} y1={H} x2={W} y2={H} stroke="rgba(242,239,233,0.5)" strokeWidth={3} />
      <path d={`${d} L ${W} ${H} L 0 ${H} Z`} fill="rgba(61,220,132,0.16)"
        style={{ clipPath: `inset(0 ${100 - linha * 100}% 0 0)` }} />
      <path d={d} fill="none" stroke={color.green} strokeWidth={8} strokeLinejoin="round" pathLength={1}
        strokeDasharray={1} strokeDashoffset={1 - linha} />
      <text x={0} y={H + 50} fill="#C9C4BC" fontFamily={font.mono} fontSize={28}>{props.eixo[0]}</text>
      <text x={W} y={H + 50} fill="#C9C4BC" fontFamily={font.mono} fontSize={28} textAnchor="end">{props.eixo[1]}</text>
    </svg></Peca>
  );
  const rotuloFim = (top: number) => (
    <Peca id="rotuloFim" style={{ position: "absolute", top, right: 0 }}><div style={{ textAlign: "right", ...appear(frame, t(em.rotulo)) }}>
      <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: 76, color: color.green }}>{props.rotuloFim.valor}</div>
      <div style={{ fontFamily: font.mono, fontSize: 24, color: color.muted }}>{props.rotuloFim.sub}</div>
    </div></Peca>
  );
  const selo = (
    <Peca id="selo" style={{ display: "inline-block" }}><div style={{
      display: "inline-block", padding: "18px 34px", borderRadius: raio.pilula,
      border: `3px solid var(--cor-texto, ${color.coral})`, color: `var(--cor-texto, ${color.coral})`,
      background: "var(--cor, transparent)", fontFamily: font.ui, fontWeight: 600,
      // texto longo encolhe em vez de quebrar a pílula em 2 linhas (base: 32 caracteres)
      fontSize: Math.round(pick(f, { story: 44, feed: 40, h: 46 }) * Math.min(1, 32 / props.selo.length)),
      whiteSpace: "nowrap", ...appear(frame, t(em.selo)),
    }}>
      {props.selo}
    </div></Peca>
  );

  if (f === "h") {
    return (
      <Cutaway durationInFrames={dur} background={fundoEscuro}>
        <div style={{ position: "absolute", top: 230, left: 140, width: 800, color: color.text }}>
          {kicker}
          {numero}
        </div>
        <div style={{ position: "absolute", top: 110, left: 980, width: W, color: color.text }}>
          <div style={{ position: "relative", height: 130 }}>{rotuloFim(0)}</div>
          {grafico}
        </div>
        {/* gráfico termina em y≈680 (110 + 130 + 380 + 60): selo logo abaixo, acima da legenda */}
        <div style={{ position: "absolute", top: 712, left: 0, right: 0, textAlign: "center" }}>{selo}</div>
      </Cutaway>
    );
  }

  return (
    <Cutaway durationInFrames={dur} background={fundoEscuro}>
      <div style={{ position: "absolute", top: pick(f, { story: 200, feed: 50, h: 0 }), left: 100, width: 880, color: color.text }}>
        {kicker}
        {numero}
        <div style={{ marginTop: pick(f, { story: 30, feed: 16, h: 0 }) }}>{grafico}</div>
        {rotuloFim(pick(f, { story: 268, feed: 214, h: 0 }))}
        {/* bloco vai de x=100 a 980: centro dele = centro do canvas (540) */}
        <div style={{ marginTop: pick(f, { story: 40, feed: 22, h: 0 }), textAlign: "center" }}>{selo}</div>
      </div>
    </Cutaway>
  );
};
