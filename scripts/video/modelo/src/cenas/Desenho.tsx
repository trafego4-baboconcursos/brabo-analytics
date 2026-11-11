import React from "react";
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, raio, useAt, useFormato } from "../theme";
import { ease, usePainel } from "./comum";
import { Peca } from "../pecas";
import type { PropsCena } from "./tipos";

const PAPEL = color.paper;

const Etiqueta: React.FC<{
  em: number; t: (s: number) => number; rot: number; size: number; cor?: string; corTexto?: string;
  children: React.ReactNode; style?: React.CSSProperties;
}> = ({ em, t, rot, size, cor, corTexto, children, style }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{
      rotate: `${rot}deg`, padding: `${Math.round(size * 0.26)}px ${Math.round(size * 0.56)}px`, background: cor ?? color.ink,
      color: corTexto ?? color.paper, fontFamily: font.ui, fontWeight: 800, fontSize: size, borderRadius: raio.etiqueta,
      boxShadow: "0 14px 30px rgba(0,0,0,0.3)", opacity: interpolate(frame, [t(em), t(em) + 4], [0, 1], clamp),
      scale: interpolate(frame, [t(em), t(em) + 8], [1.4, 1], { ...clamp, easing: ease }), ...style,
    }}>
      {children}
    </div>
  );
};

/**
 * Ilustração da personagem (imagem gerada por IA) com etiquetas que entram na fala.
 * story: imagem em tela cheia, etiquetas em x/y · feed: painel 9:16 à direita ·
 * h: metade direita recortada em 40% da altura; etiquetas empilhadas na coluna.
 */
export const Desenho: React.FC<PropsCena<"Desenho">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const painel = usePainel();
  const zoom = interpolate(frame, [0, dur], [1, 1.08]);

  if (f === "story") {
    return (
      <Cutaway durationInFrames={dur} background={PAPEL}>
        <Peca id="imagem" style={{ position: "absolute", inset: 0 }}><Img src={staticFile(props.img)} style={{
          position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", scale: zoom,
        }} /></Peca>
        {props.etiquetas.map((e, i) => (
          <Peca key={e.texto} id={`etiquetas[${i}]`} style={{ position: "absolute", left: e.x, top: e.y }}>
            <Etiqueta em={e.em} t={t} rot={e.rot} size={54} cor={e.cor} corTexto={e.corTexto}>
              {e.texto}
            </Etiqueta>
          </Peca>
        ))}
      </Cutaway>
    );
  }

  const pw = f === "h" ? 960 : painel.w;
  const px = painel.x + painel.w - pw;
  return (
    <Cutaway durationInFrames={dur} background={PAPEL}>
      <Peca id="imagem" style={{ position: "absolute", left: px, top: 0, width: pw, height: painel.h, overflow: "hidden" }}>
        <Img src={staticFile(props.img)} style={{ width: "100%", height: "100%", objectFit: "cover",
          objectPosition: f === "h" ? "50% 40%" : "50% 50%", scale: zoom }} />
      </Peca>
      {/* emenda suave entre a coluna creme e a parede creme da ilustração */}
      <div style={{ position: "absolute", left: px - 1, top: 0, width: 90, height: painel.h,
        background: `linear-gradient(90deg, ${PAPEL}, rgba(244,239,228,0))` }} />
      <div style={{
        position: "absolute", left: pick(f, { story: 0, feed: 36, h: 150 }), top: pick(f, { story: 0, feed: 90, h: 200 }),
        width: px - pick(f, { story: 0, feed: 56, h: 220 }),
        display: "flex", flexDirection: "column", alignItems: "flex-start", gap: pick(f, { story: 0, feed: 26, h: 36 }),
      }}>
        {props.etiquetas.map((e, i) => (
          <Peca key={e.texto} id={`etiquetas[${i}]`}>
            <Etiqueta em={e.em} t={t} rot={e.rot} size={pick(f, { story: 54, feed: 46, h: 68 })} cor={e.cor} corTexto={e.corTexto}>
              {e.texto}
            </Etiqueta>
          </Peca>
        ))}
      </div>
    </Cutaway>
  );
};
