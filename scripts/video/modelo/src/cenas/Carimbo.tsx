import React from "react";
import { Cutaway } from "../Cutaway";
import { font, pick, useAt, useFormato } from "../theme";
import { Handwriting, Kicker, Marker, Sheet, Stamp } from "../inserts/Paper";
import { fundoEscuro, partir } from "./comum";
import { Peca } from "../pecas";
import type { PropsCena } from "./tipos";

/** Pergunta na folha + carimbo que cai + corpo com marca-texto + anotação à mão. */
export const Carimbo: React.FC<PropsCena<"Carimbo">> = ({ start, dur, props }) => {
  const t = useAt(start);
  const f = useFormato();
  const [antes, alvo, depois] = partir(props.corpo, props.destaque.texto);
  return (
    <Cutaway durationInFrames={dur} background={fundoEscuro}>
      <Sheet tilt={3} width={pick(f, { story: 900, feed: 900, h: 1320 })} top={pick(f, { story: 190, feed: 50, h: 90 })}>
        <Peca id="kicker"><Kicker>{props.kicker}</Kicker></Peca>
        <div style={{ display: f === "h" ? "flex" : "block", alignItems: "center", gap: 60 }}>
          <Peca id="pergunta" style={{ flex: "1 1 auto" }}><div style={{ fontFamily: font.serif, fontWeight: 700, fontSize: pick(f, { story: 96, feed: 84, h: 96 }), lineHeight: 1.05,
            // h: pergunta curta fica numa linha ao lado do carimbo; longa quebra (senão empurra o carimbo para fora)
            whiteSpace: f === "h" && props.pergunta.length <= 20 ? "nowrap" : "normal" }}>
            {props.pergunta}
          </div></Peca>
          <Peca id="carimbo" style={{ margin: pick(f, { story: "40px 0 30px", feed: "26px 0 20px", h: "0" }), flexShrink: 0 }}>
            <Stamp from={t(props.carimbo.em)} style={{ fontSize: pick(f, { story: 92, feed: 78, h: 92 }), whiteSpace: "nowrap" }}>
              {props.carimbo.texto}
            </Stamp>
          </Peca>
        </div>
        <Peca id="corpo" style={{ marginTop: f === "h" ? 36 : 0 }}><div style={{ fontFamily: font.serif, fontSize: pick(f, { story: 48, feed: 42, h: 50 }), lineHeight: 1.35 }}>
          {antes}
          <Marker at={props.destaque.em} startSec={start}>
            {alvo}
          </Marker>
          {depois}
        </div></Peca>
        <Peca id="mao"><Handwriting from={t(props.mao.em)} style={{ marginTop: pick(f, { story: 30, feed: 16, h: 24 }), fontSize: pick(f, { story: 64, feed: 54, h: 64 }) }}>
          {props.mao.texto}
        </Handwriting></Peca>
      </Sheet>
    </Cutaway>
  );
};
