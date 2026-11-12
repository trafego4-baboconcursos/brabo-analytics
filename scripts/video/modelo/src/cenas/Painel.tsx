import React from "react";
import { Video } from "@remotion/media";
import { Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, raio, useAt, useFormato } from "../theme";
import { Peca } from "../pecas";
import { appear, ease, partir } from "./comum";
import type { BlocoPainel, PropsCena } from "./tipos";

/*
 * Painel "noite" (referência do AD359): ilustração chapada de fundo (gerada por IA) com
 * leve zoom, véu escuro embaixo, HUD no topo (pílula com ponto vermelho à esquerda,
 * etiqueta amarela do assunto à direita), título grande com palavra em amarelo e um bloco
 * de conteúdo: contador, barras, ordem numerada, lista ✓/✗ ou carimbo. O bloco termina
 * acima da legenda (story y≈1350).
 */

const amarelo = color.amarelo;
// tema dia: palavra de destaque do título em madeira quente (paleta do bruto do AD359)
const DESTAQUE_DIA = color.madeira;

const Hud: React.FC<{ hud?: string; tag: string; tagEm: number }> = ({ hud, tag, tagEm }) => {
  const frame = useCurrentFrame();
  const f = useFormato();
  const pisca = Math.floor(frame / 15) % 2 === 0 ? 1 : 0.25;
  const topo = pick(f, { story: 120, feed: 40, h: 40 });
  return (
    <>
      {hud && (
        <Peca id="hud" style={{ position: "absolute", left: pick(f, { story: 60, feed: 40, h: 60 }), top: topo }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 22px", borderRadius: raio.pilula,
            background: "rgba(14,22,38,0.82)", border: `2px solid ${color.navyLine}`, color: "white",
            fontFamily: font.mono, fontWeight: 700, fontSize: 30, letterSpacing: 2 }}>
            <span style={{ width: 16, height: 16, borderRadius: 99, background: color.vermelho, opacity: pisca }} />
            {hud}
          </div>
        </Peca>
      )}
      <Peca id="tag" style={{ position: "absolute", right: pick(f, { story: 60, feed: 40, h: 60 }), top: topo }}>
        <div style={{ padding: "12px 24px", borderRadius: raio.pilula, background: `var(--cor, ${amarelo})`,
          color: `var(--cor-texto, ${color.navy})`, fontFamily: font.ui, fontWeight: 800, fontSize: 30, letterSpacing: 1,
          textTransform: "uppercase", ...appear(frame, tagEm) }}>
          {tag}
        </div>
      </Peca>
    </>
  );
};

const Bloco: React.FC<{ b: BlocoPainel; t: (s: number) => number; cartao?: boolean }> = ({ b, t, cartao }) => {
  const frame = useCurrentFrame();
  const f = useFormato();
  const largura = pick(f, { story: 900, feed: 860, h: 1000 });

  if (b.tipo === "contador") {
    const n = Math.round(interpolate(frame, [t(b.conta[0]), t(b.conta[1])], [b.de ?? 0, b.ate], { ...clamp, easing: ease }));
    return (
      <Peca id="numero" style={{ textAlign: "center", ...appear(frame, t(b.conta[0])),
        // dia: número num cartão navy (amarelo sobre céu claro não lê)
        ...(cartao ? { background: `var(--cor, ${color.navy})`, borderRadius: 32, padding: "30px 60px 36px",
          border: `3px solid ${amarelo}`, boxShadow: "0 20px 50px rgba(0,0,0,0.3)" } : {}) }}>
        <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 230, feed: 170, h: 200 }), lineHeight: 1,
          color: `var(--cor-texto, ${amarelo})`, letterSpacing: -8, textShadow: "0 8px 40px rgba(0,0,0,0.5)" }}>
          {b.prefixo ?? ""}{n.toLocaleString("pt-BR")}{b.sufixo ?? ""}
        </div>
        <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 54, feed: 44, h: 50 }), color: "white",
          textTransform: "uppercase", letterSpacing: 2, marginTop: 10 }}>{b.rotulo}</div>
      </Peca>
    );
  }

  if (b.tipo === "barras") {
    const cores = { amarelo, verde: color.green, vermelho: color.vermelho };
    return (
      <div style={{ width: largura, display: "flex", flexDirection: "column", gap: 26 }}>
        {b.itens.map((it, i) => {
          const cheio = interpolate(frame, [t(it.em), t(it.em) + 24], [0, it.fracao], { ...clamp, easing: Easing.out(Easing.cubic) });
          return (
            <Peca key={i} id={`itens[${i}]`} style={appear(frame, t(it.em))}>
              <div style={{ padding: "26px 32px", borderRadius: 22, background: `var(--cor, ${color.navyCard})`,
                border: `2px solid ${color.navyLine}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", color: "white",
                  fontFamily: font.ui, fontWeight: 800, fontSize: 40, textTransform: "uppercase" }}>
                  <span>{it.rotulo}</span>
                  <span style={{ color: cores[it.cor ?? "amarelo"], fontFamily: font.mono, fontSize: 38 }}>{it.valor}</span>
                </div>
                <div style={{ height: 18, borderRadius: 99, background: "rgba(255,255,255,0.12)", marginTop: 18, overflow: "hidden" }}>
                  <div style={{ width: `${cheio * 100}%`, height: "100%", borderRadius: 99, background: cores[it.cor ?? "amarelo"] }} />
                </div>
              </div>
            </Peca>
          );
        })}
      </div>
    );
  }

  if (b.tipo === "ordem" || b.tipo === "lista") {
    // dia com 4+ itens: 2 colunas, baixinho, para não cobrir o rosto do personagem
    const duas = cartao && f !== "h" && b.itens.length > 3;
    const fonte = duas ? pick(f, { story: 34, feed: 30, h: 30 }) : pick(f, { story: 44, feed: 38, h: 38 });
    return (
      <div style={duas
        ? { width: pick(f, { story: 960, feed: 960, h: 960 }), display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }
        : { width: largura, display: "flex", flexDirection: "column", gap: 22 }}>
        {b.itens.map((it, i) => {
          const marca = b.tipo === "ordem" ? String(i + 1) : it.ok === false ? "✕" : "✓";
          const corMarca = b.tipo === "ordem" ? amarelo : it.ok === false ? color.vermelho : color.green;
          const on = interpolate(frame, [t(it.em), t(it.em) + 10], [0.4, 1], { ...clamp, easing: Easing.back(2) });
          return (
            <Peca key={i} id={`itens[${i}]`} style={appear(frame, t(it.em))}>
              <div style={{ display: "flex", alignItems: "center", gap: duas ? 16 : 26, padding: duas ? "20px 20px" : "24px 30px",
                borderRadius: 22, height: duas ? "100%" : undefined, boxSizing: "border-box",
                background: `var(--cor, ${color.navyCard})`, border: `3px solid ${b.tipo === "ordem" ? amarelo : color.navyLine}`,
                color: `var(--cor-texto, white)`, fontFamily: font.ui, fontWeight: 800, fontSize: fonte, lineHeight: 1.15 }}>
                <div style={{ width: duas ? 54 : 66, height: duas ? 54 : 66, flexShrink: 0, borderRadius: 99, display: "flex",
                  alignItems: "center", justifyContent: "center", background: corMarca, color: color.navy,
                  fontSize: duas ? 32 : 38, scale: on }}>{marca}</div>
                {it.texto}
              </div>
            </Peca>
          );
        })}
      </div>
    );
  }

  // carimbo
  const cai = interpolate(frame, [t(b.em), t(b.em) + 7], [2.2, 1], { ...clamp, easing: Easing.bezier(0.5, 0, 0.75, 0) });
  return (
    <Peca id="carimbo" style={{ textAlign: "center" }}>
      <div style={{ display: "inline-block", padding: "10px 36px", border: `8px solid var(--cor-texto, ${color.vermelho})`,
        borderRadius: 16, color: `var(--cor-texto, ${color.vermelho})`, fontFamily: font.stamp, fontSize: pick(f, { story: 96, feed: 80, h: 90 }),
        letterSpacing: 4, rotate: "-6deg", scale: cai, opacity: interpolate(frame, [t(b.em), t(b.em) + 3], [0, 1], clamp),
        background: "rgba(14,22,38,0.75)" }}>
        {b.texto}
      </div>
    </Peca>
  );
};

export const Painel: React.FC<PropsCena<"Painel">> = ({ start, dur, props }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const { width, height } = useVideoConfig();
  const zoom = interpolate(frame, [0, dur], [1.02, 1.1]);
  const titulo = props.titulo;
  const dia = props.tema === "dia";
  const [antes, alvo, depois] = titulo ? partir(titulo.texto, titulo.destaque || titulo.texto.slice(0, 0)) : ["", "", ""];
  // a ilustração é 9:16. story/feed: cobre a tela (caixa calculada — o <Video> não respeita object-fit);
  // h: painel 9:16 de altura cheia à direita, texto e bloco na coluna da esquerda (rosto não é cortado)
  const painel = f === "h";
  const pw = Math.round((height * 9) / 16);
  const cw = painel ? pw : Math.max(width, (height * 9) / 16);
  const ch = painel ? height : (cw * 16) / 9;
  const caixa: React.CSSProperties = painel
    ? { position: "absolute", right: 0, top: 0, width: pw, height }
    : { position: "absolute", left: (width - cw) / 2, top: (height - ch) / 2, width: cw, height: ch };
  const midia: React.CSSProperties = { position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", scale: zoom };
  const colunaDireita = painel ? pw : 0;
  return (
    <Cutaway durationInFrames={dur} background={dia ? color.creme : color.navy}>
      {(props.fundo || props.fundoVideo) && (
        <Peca id="imagem" style={{ ...caixa, overflow: "hidden" }}>
          {props.fundoVideo
            // ilustração animada (IA, ida e volta para cobrir a cena); o 1º quadro é a própria `fundo`
            ? <Video src={staticFile(props.fundoVideo)} muted style={midia} />
            : <Img src={staticFile(props.fundo!)} style={midia} />}
        </Peca>
      )}
      {painel ? (
        // h: emenda suave entre a coluna lisa e o painel da ilustração
        <div style={{ position: "absolute", top: 0, bottom: 0, right: pw - 140, width: 160, background: dia
          ? "linear-gradient(90deg, rgba(239,231,220,1), rgba(239,231,220,0))"
          : "linear-gradient(90deg, rgba(14,22,38,1), rgba(14,22,38,0))" }} />
      ) : (
        /* véu: noite = topo e base escuros; dia = topo creme (título navy) e base escura (legenda branca) */
        <div style={{ position: "absolute", inset: 0, background: dia
          ? "linear-gradient(180deg, rgba(239,231,220,0.92) 0%, rgba(239,231,220,0.55) 24%, rgba(239,231,220,0) 40%, rgba(27,34,54,0) 58%, rgba(27,34,54,0.85) 100%)"
          : "linear-gradient(180deg, rgba(14,22,38,0.85) 0%, rgba(14,22,38,0.35) 28%, rgba(14,22,38,0.35) 55%, rgba(14,22,38,0.92) 100%)" }} />
      )}
      {painel && dia && (
        // h dia: base escura só na coluna, para a legenda branca ler
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 260,
          background: "linear-gradient(180deg, rgba(27,34,54,0), rgba(27,34,54,0.8))" }} />
      )}
      <Hud hud={props.hud} tag={props.tag} tagEm={t(start + 0.2)} />
      {titulo && (
        <Peca id="titulo" style={{ position: "absolute", left: pick(f, { story: 70, feed: 60, h: 100 }),
          right: pick(f, { story: 70, feed: 60, h: colunaDireita + 60 }), top: pick(f, { story: 260, feed: 120, h: 140 }),
          textAlign: "center", ...appear(frame, t(titulo.em)) }}>
          <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 84, feed: 64, h: 72 }), lineHeight: 1.05,
            color: dia ? color.navy : "white", textTransform: "uppercase", whiteSpace: "pre-line",
            textShadow: dia ? "0 2px 16px rgba(239,231,220,0.9)" : "0 6px 30px rgba(0,0,0,0.6)" }}>
            {antes}<span style={{ color: dia ? DESTAQUE_DIA : amarelo }}>{alvo}</span>{depois}
          </div>
        </Peca>
      )}
      {/* dia (story/feed): personagem no meio da ilustração → bloco ancorado embaixo, logo acima da legenda */}
      <div style={{ position: "absolute", left: 0, right: colunaDireita, display: "flex", justifyContent: "center",
        ...(dia && !painel ? { bottom: pick(f, { story: 540, feed: 196, h: 0 }) }
          : { top: pick(f, { story: titulo ? 600 : 460, feed: 330, h: 360 }) }) }}>
        <Bloco b={props.bloco} t={t} cartao={dia} />
      </div>
    </Cutaway>
  );
};
