import React from "react";
import { Cutaway } from "../Cutaway";
import { font, pick, useFormato } from "../theme";
import { Kicker, Marker, Sheet } from "../inserts/Paper";
import { fundoEscuro, partir } from "./comum";
import type { PropsCena } from "./tipos";

/** Folha de papel com título e corpo; marca-texto no destaque, na palavra falada. */
export const Manchete: React.FC<PropsCena<"Manchete">> = ({ start, dur, props }) => {
  const f = useFormato();
  const [antes, alvo, depois] = partir(props.corpo, props.destaque.texto);
  return (
    <Cutaway durationInFrames={dur} background={fundoEscuro}>
      <Sheet width={pick(f, { story: 900, feed: 900, h: 1320 })} top={pick(f, { story: 190, feed: 80, h: 130 })}>
        <Kicker>{props.kicker}</Kicker>
        <div style={{ fontFamily: font.serif, fontWeight: 700, fontSize: pick(f, { story: 104, feed: 92, h: 104 }), lineHeight: 1.02 }}>
          {props.titulo}
        </div>
        <div style={{ fontFamily: font.serif, fontSize: pick(f, { story: 48, feed: 44, h: 50 }), lineHeight: 1.35, marginTop: 34 }}>
          {antes}
          <Marker at={props.destaque.em} startSec={start}>
            {alvo}
          </Marker>
          {depois}
        </div>
      </Sheet>
    </Cutaway>
  );
};
