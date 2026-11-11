import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, raio, useAt, useFormato } from "../theme";
import { appear, fundoEscuro, partir, usePainel } from "./comum";
import { Peca } from "../pecas";
import type { PropsCena, PropsRota } from "./tipos";

const caminho = (pts: [number, number][]) => pts.map(([x, y], i) => `${i ? "L" : "M"} ${x} ${y}`).join(" ");

const rotuloCume = (flag: number, size: number): React.CSSProperties => ({
  whiteSpace: "nowrap", padding: "16px 30px", borderRadius: raio.pilula, background: color.coral, color: "white",
  fontFamily: font.ui, fontWeight: 800, fontSize: size, boxShadow: "0 14px 34px rgba(0,0,0,0.35)",
  opacity: flag, scale: interpolate(flag, [0, 1], [0.6, 1]), transformOrigin: "0% 50%",
});

/**
 * Ilustração + estrada + trilha + bandeira, tudo em coordenadas 1080×1920 (o story).
 * A imagem entra como "cover" pelo tamanho original; em feed/h o bloco inteiro é reduzido.
 */
const MapaDesenhado: React.FC<{ props: PropsRota; p: number; trilha: number; flag: number; zoom: number; rotulo: boolean }> = ({
  props, p, trilha, flag, zoom, rotulo,
}) => {
  const [iw, ih] = props.imagemTamanho;
  const altura = Math.round((1080 * ih) / iw);
  const topo = Math.round((1920 - altura) / 2);
  const { cume } = props;
  const [x0, y0] = props.estrada[0];
  const traco = { fill: "none", strokeLinecap: "round", strokeLinejoin: "round", pathLength: 1, strokeDasharray: 1 } as const;
  const estrada = caminho(props.estrada);
  const subida = caminho(props.trilha);
  return (
    <AbsoluteFill style={{ width: 1080, height: 1920, scale: zoom, transformOrigin: "50% 45%" }}>
      <Img src={staticFile(props.imagem)} style={{ position: "absolute", left: 0, top: topo, width: 1080, height: altura }} />
      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        {/* contorno escuro por baixo: a rota coral destaca da estrada pintada */}
        <path d={estrada} {...traco} stroke="rgba(17,17,17,0.55)" strokeWidth={22} strokeDashoffset={1 - p} />
        <path d={estrada} {...traco} stroke={color.coral} strokeWidth={13} strokeDashoffset={1 - p} />
        <path d={subida} {...traco} stroke="rgba(17,17,17,0.55)" strokeWidth={20} strokeDashoffset={1 - trilha} />
        <path d={subida} {...traco} stroke={color.coral} strokeWidth={11} strokeDashoffset={1 - trilha} />
        <circle cx={x0} cy={y0} r={22} fill={color.night} stroke={color.coral} strokeWidth={10} />
        <g style={{ opacity: flag > 0 ? 1 : 0 }}>
          <g style={{ scale: `1 ${flag}`, transformOrigin: `${cume.x}px ${cume.y}px`, transformBox: "view-box" }}>
            <line x1={cume.x} y1={cume.y} x2={cume.x} y2={cume.y - 150} stroke={color.text} strokeWidth={8} strokeLinecap="round" />
            <polygon points={`${cume.x},${cume.y - 150} ${cume.x + 110},${cume.y - 122} ${cume.x},${cume.y - 94}`} fill={color.coral} />
          </g>
        </g>
      </svg>
      {rotulo && (
        <Peca id="rotuloCume" style={{ position: "absolute", left: cume.x + 130, top: cume.y - 190 }}><div style={rotuloCume(flag, 54)}>
          {props.rotuloCume}
        </div></Peca>
      )}
    </AbsoluteFill>
  );
};

export const Rota: React.FC<PropsCena<"Rota">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const painel = usePainel();
  const { em } = props;
  const p = interpolate(frame, [t(em.estrada[0]), t(em.estrada[1])], [0, 1], { ...clamp, easing: Easing.inOut(Easing.quad) });
  const trilha = interpolate(frame, [t(em.trilha[0]), t(em.trilha[1])], [0, 1], { ...clamp, easing: Easing.inOut(Easing.quad) });
  const flag = interpolate(frame, [t(em.bandeira), t(em.bandeira) + 10], [0, 1], { ...clamp, easing: Easing.back(2) });
  const zoom = interpolate(frame, [0, dur], [1, 1.06]);
  const [antes, alvo, depois] = partir(props.titulo, props.tituloDestaque.texto);

  const titulo = (size: number, sombra: boolean) => (
    <>
      <Peca id="kicker"><div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: "#C9C4BC" }}>{props.kicker}</div></Peca>
      <Peca id="titulo"><div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: size, lineHeight: 1.05, color: color.text,
        textShadow: sombra ? "0 4px 24px rgba(0,0,0,0.6)" : "none" }}>
        {antes}
        <span style={{ color: color.coral,
          opacity: interpolate(frame, [t(props.tituloDestaque.em), t(props.tituloDestaque.em) + 6], [0.25, 1], clamp) }}>
          {alvo}
        </span>
        {depois}
      </div></Peca>
    </>
  );
  const selo: React.CSSProperties = {
    padding: "20px 34px", borderRadius: raio.pilula, background: color.card,
    border: `2px solid ${color.line}`, color: color.text, fontFamily: font.ui, fontWeight: 800, fontSize: 52,
    boxShadow: "0 16px 40px rgba(0,0,0,0.5)", ...appear(frame, t(props.selo.em)),
  };

  if (f === "story") {
    return (
      <Cutaway durationInFrames={dur} background={color.night}>
        <MapaDesenhado props={props} p={p} trilha={trilha} flag={flag} zoom={zoom} rotulo />
        <div style={{
          position: "absolute", top: 150, left: 90, right: 90, ...appear(frame, t(start + 0.3)),
          // sai de cena quando a trilha chega ao cume, para a bandeira ser o destaque
          ...(frame > t(em.saiTitulo) ? { opacity: interpolate(frame, [t(em.saiTitulo), t(em.saiTitulo) + 12], [1, 0], clamp) } : {}),
        }}>
          {titulo(84, true)}
        </div>
        <Peca id="selo" style={{ position: "absolute", top: 1000, left: 60 }}><div style={selo}>{props.selo.texto}</div></Peca>
      </Cutaway>
    );
  }

  // feed/h: mapa inteiro no painel da direita (reduzido); título, selo e rótulo do cume na coluna
  const k = painel.h / 1920;
  return (
    <Cutaway durationInFrames={dur} background={fundoEscuro}>
      <div style={{ position: "absolute", left: painel.x, top: 0, width: painel.w, height: painel.h, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: 1920, scale: k, transformOrigin: "0 0" }}>
          <MapaDesenhado props={props} p={p} trilha={trilha} flag={flag} zoom={zoom} rotulo={false} />
        </div>
      </div>
      <div style={{
        position: "absolute", left: pick(f, { story: 0, feed: 40, h: 150 }), top: pick(f, { story: 0, feed: 90, h: 200 }),
        width: painel.colW - pick(f, { story: 0, feed: 70, h: 300 }), ...appear(frame, t(start + 0.3)),
      }}>
        {titulo(pick(f, { story: 84, feed: 58, h: 96 }), false)}
        <Peca id="selo" style={{ display: "inline-block", marginTop: pick(f, { story: 0, feed: 44, h: 70 }) }}><div style={selo}>{props.selo.texto}</div></Peca>
        <div style={{ marginTop: pick(f, { story: 0, feed: 34, h: 50 }) }}>
          <Peca id="rotuloCume" style={{ display: "inline-block" }}><div style={rotuloCume(flag, pick(f, { story: 54, feed: 52, h: 64 }))}>⚑ {props.rotuloCume}</div></Peca>
        </div>
      </div>
    </Cutaway>
  );
};
