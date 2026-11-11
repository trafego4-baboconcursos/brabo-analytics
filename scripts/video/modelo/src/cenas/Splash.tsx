import React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, useAt, useFormato } from "../theme";
import { appear } from "./comum";
import { Peca } from "../pecas";
import type { PropsCena } from "./tipos";

/**
 * Abertura ou transição: faixa coral atravessa a tela e o título entra em escala
 * sobre fundo night. Conteúdo acima da faixa da legenda em todos os formatos.
 */
export const Splash: React.FC<PropsCena<"Splash">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const at = t(props.em);
  const faixa = interpolate(frame, [at - 6, at + 6], [-110, 0], { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) });
  const centro = pick(f, { story: 720, feed: 400, h: 400 });
  const meiaFaixa = pick(f, { story: 136, feed: 104, h: 112 });
  const tamImg = pick(f, { story: 520, feed: 272, h: 272 });
  return (
    <Cutaway durationInFrames={dur} background={color.night}>
      {props.imagem && (
        // elemento-herói logo acima da faixa: entra com salto um pouco antes do título
        <Peca id="imagem" style={{ position: "absolute", width: tamImg, height: tamImg,
          left: `calc(50% - ${tamImg / 2}px)`, top: centro - meiaFaixa - tamImg + 24 }}><Img src={staticFile(props.imagem)} style={{
          width: tamImg, height: tamImg, objectFit: "contain", display: "block",
          opacity: interpolate(frame, [at - 8, at], [0, 1], clamp),
          scale: interpolate(frame, [at - 8, at + 6], [0.6, 1], { ...clamp, easing: Easing.back(1.8), output: "perceptual-scale" }),
          translate: interpolate(frame, [at - 8, at + 6], ["0px 40px", "0px 0px"], { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) }),
        }} /></Peca>
      )}
      <Peca id="faixa" style={{ position: "absolute", left: 0, right: 0, top: centro - meiaFaixa }}><div style={{
        height: pick(f, { story: 272, feed: 208, h: 224 }), background: color.coral,
        translate: `${faixa}% 0px`, rotate: "-3deg",
      }} /></Peca>
      <div style={{
        position: "absolute", left: pick(f, { story: 80, feed: 80, h: 160 }), right: pick(f, { story: 80, feed: 80, h: 160 }),
        top: centro, translate: "0 -50%", textAlign: "center", color: color.text,
      }}>
        <Peca id="titulo"><div style={{
          fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 120, feed: 96, h: 112 }), lineHeight: 1,
          letterSpacing: -3, whiteSpace: "pre-line",
          scale: interpolate(frame, [at, at + 14], [1.25, 1], { ...clamp, easing: Easing.back(1.6), output: "perceptual-scale" }),
          opacity: interpolate(frame, [at, at + 4], [0, 1], clamp),
        }}>
          {props.titulo}
        </div></Peca>
        {props.subtitulo && (
          <Peca id="subtitulo" style={{ marginTop: 24 }}><div style={{ fontFamily: font.ui, fontWeight: 600, fontSize: pick(f, { story: 48, feed: 40, h: 44 }),
            ...appear(frame, at + 10) }}>
            {props.subtitulo}
          </div></Peca>
        )}
      </div>
    </Cutaway>
  );
};
