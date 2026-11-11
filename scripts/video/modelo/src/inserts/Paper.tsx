import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Highlight } from "@remotion/rough-notation";
import { clamp, color, font, useAt } from "../theme";
import { Peca } from "../pecas";

/** Folha de papel (estilo "headline" da referência): leve inclinação que endireita. */
export const Sheet: React.FC<{ children: React.ReactNode; width?: number; tilt?: number; top?: number }> = ({
  children,
  width = 900,
  tilt = -3,
  top = 190,
}) => {
  const frame = useCurrentFrame();
  const { width: W } = useVideoConfig();
  return (
    <Peca id="folha" style={{ position: "absolute", top, left: (W - width) / 2, width }}>
    <div
      style={{
        background: `var(--cor, ${color.paper})`,
        color: color.ink,
        padding: "56px 60px 64px",
        boxShadow: "0 40px 80px rgba(0,0,0,0.55), 0 4px 10px rgba(0,0,0,0.3)",
        rotate: interpolate(frame, [0, 24], [`${tilt}deg`, `${tilt / 3}deg`], {
          ...clamp,
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}
    >
      {children}
    </div>
    </Peca>
  );
};

export const Kicker: React.FC<{ children: React.ReactNode; dark?: boolean }> = ({ children, dark }) => (
  <div
    style={{
      fontFamily: font.mono,
      fontSize: 26,
      letterSpacing: 3,
      textTransform: "uppercase",
      color: dark ? color.muted : "#6B655C",
      borderBottom: `2px solid ${dark ? color.line : "#1A1A1A"}`,
      paddingBottom: 18,
      marginBottom: 30,
    }}
  >
    {children}
  </div>
);

/** Marca-texto que passa no tempo exato da palavra falada. */
export const Marker: React.FC<{ at: number; startSec: number; children: React.ReactNode }> = ({
  at,
  startSec,
  children,
}) => {
  const frame = useCurrentFrame();
  const t = useAt(startSec);
  return (
    <Highlight color={color.highlighter} progress={interpolate(frame, [t(at), t(at) + 10], [0, 1], clamp)}>
      {children}
    </Highlight>
  );
};

/** Carimbo de borracha que cai na folha. */
export const Stamp: React.FC<{ from: number; children: React.ReactNode; rotate?: number; style?: React.CSSProperties }> = ({
  from,
  children,
  rotate = -8,
  style,
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        display: "inline-block",
        fontFamily: font.stamp,
        fontSize: 92,
        letterSpacing: 4,
        color: `var(--cor-texto, ${color.marker})`,
        border: `8px solid var(--cor-texto, ${color.marker})`,
        borderRadius: 14,
        padding: "4px 30px",
        mixBlendMode: "multiply",
        rotate: `${rotate}deg`,
        opacity: interpolate(frame, [from, from + 3], [0, 0.92], clamp),
        scale: interpolate(frame, [from, from + 7], [2.2, 1], {
          ...clamp,
          easing: Easing.bezier(0.5, 0, 0.75, 0),
          output: "perceptual-scale",
        }),
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** Texto escrito à mão que aparece da esquerda para a direita. */
export const Handwriting: React.FC<{ from: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  from,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        fontFamily: font.hand,
        fontWeight: 700,
        fontSize: 64,
        color: color.marker,
        clipPath: `inset(0 ${interpolate(frame, [from, from + 18], [100, 0], clamp)}% 0 0)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
