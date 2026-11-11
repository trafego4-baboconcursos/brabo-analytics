import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Cutaway } from "../Cutaway";
import { clamp, color, font, pick, useAt, useFormato } from "../theme";
import { Handwriting, Kicker, Marker, Sheet, Stamp } from "./Paper";

/*
 * Cada cena tem layout por formato: story 1080×1920 (o original, valores intocados),
 * feed 1080×1080 e h 1920×1080. Em feed/h a legenda ocupa a faixa de baixo
 * (feed y≈830, h y≈870), então o conteúdo das cenas fica acima dela.
 * Imagens verticais (desenhos, mapa) viram tela dividida: painel 9:16 inteiro à
 * direita + coluna de texto à esquerda — nada da ilustração é cortado.
 */

type P = { start: number; dur: number };

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const appear = (frame: number, at: number) => ({
  opacity: interpolate(frame, [at, at + 8], [0, 1], clamp),
  translate: interpolate(frame, [at, at + 12], ["0px 24px", "0px 0px"], { ...clamp, easing: ease }),
});
const darkBg = `radial-gradient(120% 80% at 50% 20%, #232323 0%, ${color.night} 70%)`;
const PAPEL = "#F4EFE4";

/** Painel vertical 9:16 de altura cheia, encostado na direita (feed/h). */
const usePainel = () => {
  const { width, height } = useVideoConfig();
  const w = Math.round((height * 9) / 16);
  return { w, h: height, x: width - w, colW: width - w };
};

/* Desenhos da personagem (imagens geradas por IA em public/) ----------------- */
/** [tempo absoluto, texto, x, y, rotação] — x/y só valem no story */
type Etiqueta = [number, string, number, number, number];

const Etiquetinha: React.FC<{ at: number; t: (s: number) => number; r: number; size: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  at, t, r, size, children, style,
}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{
      rotate: `${r}deg`, padding: `${Math.round(size * 0.26)}px ${Math.round(size * 0.56)}px`, background: color.ink,
      color: color.paper, fontFamily: font.ui, fontWeight: 800, fontSize: size, borderRadius: 14,
      boxShadow: "0 14px 30px rgba(0,0,0,0.3)", opacity: interpolate(frame, [t(at), t(at) + 4], [0, 1], clamp),
      scale: interpolate(frame, [t(at), t(at) + 8], [1.4, 1], { ...clamp, easing: ease }), ...style,
    }}>
      {children}
    </div>
  );
};

const Desenho: React.FC<P & { img: string; etiquetas: Etiqueta[] }> = ({ start, dur, img, etiquetas }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const painel = usePainel();
  const zoom = interpolate(frame, [0, dur], [1, 1.08]);

  if (f === "story") {
    return (
      <Cutaway durationInFrames={dur} background={PAPEL}>
        <Img src={staticFile(img)} style={{
          position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", scale: zoom,
        }} />
        {etiquetas.map(([at, txt, x, y, r]) => (
          <Etiquetinha key={txt} at={at} t={t} r={r} size={54} style={{ position: "absolute", left: x, top: y }}>
            {txt}
          </Etiquetinha>
        ))}
      </Cutaway>
    );
  }

  // feed: ilustração inteira no painel 9:16 da direita · h: metade direita, recortada
  // em 40% da altura (cabe o balão da formatura, a personagem e a borda da mesa)
  const pw = f === "h" ? 960 : painel.w;
  const px = painel.x + painel.w - pw;
  return (
    <Cutaway durationInFrames={dur} background={PAPEL}>
      <div style={{ position: "absolute", left: px, top: 0, width: pw, height: painel.h, overflow: "hidden" }}>
        <Img src={staticFile(img)} style={{ width: "100%", height: "100%", objectFit: "cover",
          objectPosition: f === "h" ? "50% 40%" : "50% 50%", scale: zoom }} />
      </div>
      {/* emenda suave entre a coluna creme e a parede creme da ilustração */}
      <div style={{ position: "absolute", left: px - 1, top: 0, width: 90, height: painel.h,
        background: `linear-gradient(90deg, ${PAPEL}, rgba(244,239,228,0))` }} />
      <div style={{
        position: "absolute", left: pick(f, { story: 0, feed: 36, h: 150 }), top: pick(f, { story: 0, feed: 90, h: 200 }),
        width: px - pick(f, { story: 0, feed: 56, h: 220 }),
        display: "flex", flexDirection: "column", alignItems: "flex-start", gap: pick(f, { story: 0, feed: 26, h: 36 }),
      }}>
        {etiquetas.map(([at, txt, , , r]) => (
          <Etiquetinha key={txt} at={at} t={t} r={r} size={pick(f, { story: 54, feed: 46, h: 68 })}>
            {txt}
          </Etiquetinha>
        ))}
      </div>
    </Cutaway>
  );
};

/** 0 · Dona de casa: "mulher que trabalha, cuida de casa…" (3,4 → 9,0 s) */
export const DonaDeCasa: React.FC<P> = (p) => (
  <Desenho {...p} img="dona-de-casa-original.jpg" etiquetas={[
    [4.4, "trabalha", 90, 190, -4],
    [4.82, "cuida da casa", 430, 290, 3],
    [6.25, "pouco tempo pra estudar", 120, 390, -2],
  ]} />
);

/** 0b · Sem faculdade (19,13 → 22,4 s) */
export const SemFaculdade: React.FC<P> = (p) => (
  // story: o balão de pensamento (formatura) ocupa a parede à esquerda (x≈30–505, y≈290–775):
  // etiquetas acima dele e à direita, sem cobrir o balão
  <Desenho {...p} img="dona-de-casa-faculdade.jpg" etiquetas={[
    [19.66, "faculdade? não", 40, 150, -4],
    [20.8, "só ensino médio", 520, 310, 3],
  ]} />
);

/** 0c · Tem filho (52,7 → 57,1 s) */
export const TemFilho: React.FC<P> = (p) => (
  <Desenho {...p} img="dona-de-casa-filho.jpg" etiquetas={[
    [53.82, "trabalha", 90, 190, -4],
    [54.28, "cuida da casa", 430, 290, 3],
    [55.12, "tem filho", 160, 390, -2],
  ]} />
);

/* 1 · Manchete: o cargo ----------------------------------------------------- */
export const CargoManchete: React.FC<P> = ({ start, dur }) => {
  const f = useFormato();
  return (
    <Cutaway durationInFrames={dur} background={darkBg}>
      <Sheet width={pick(f, { story: 900, feed: 900, h: 1320 })} top={pick(f, { story: 190, feed: 80, h: 130 })}>
        <Kicker>Ficha do concurso · INSS</Kicker>
        <div style={{ fontFamily: font.serif, fontWeight: 700, fontSize: pick(f, { story: 104, feed: 92, h: 104 }), lineHeight: 1.02 }}>
          Técnico do Seguro Social
        </div>
        <div style={{ fontFamily: font.serif, fontSize: pick(f, { story: 48, feed: 44, h: 50 }), lineHeight: 1.35, marginTop: 34 }}>
          Cargo da autarquia federal. Exige só{" "}
          <Marker at={32.4} startSec={start}>
            nível médio
          </Marker>
          : não precisa de faculdade.
        </div>
      </Sheet>
    </Cutaway>
  );
};

/* 2 · Gráfico: salário ------------------------------------------------------ */
export const SalarioGrafico: React.FC<P> = ({ start, dur }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const valor = Math.round(interpolate(frame, [t(34.1), t(35.5)], [0, 7234], { ...clamp, easing: ease }));
  const linha = interpolate(frame, [t(36.1), t(38.9)], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  // degraus de progressão na carreira: 7.234 → ~11.000
  const pts = [7234, 7234, 7700, 7700, 8300, 8300, 9000, 9000, 9900, 9900, 11000];
  const W = pick(f, { story: 880, feed: 880, h: 820 });
  const H = pick(f, { story: 440, feed: 290, h: 470 });
  const min = 6500, max = 13800;
  const d = pts
    .map((v, i) => `${i === 0 ? "M" : "L"} ${(i / (pts.length - 1)) * W} ${H - ((v - min) / (max - min)) * H}`)
    .join(" ");

  const kicker = (
    <div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.muted }}>
      SALÁRIO INICIAL · TÉCNICO DO INSS
    </div>
  );
  const numero = (
    <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 190, feed: 150, h: 210 }), letterSpacing: -6, lineHeight: 1.1 }}>
      <span style={{ fontSize: pick(f, { story: 96, feed: 76, h: 104 }), verticalAlign: "top", marginRight: 10 }}>R$</span>
      {valor.toLocaleString("pt-BR")}
    </div>
  );
  const grafico = (
    <svg width={W} height={H + 60} style={{ overflow: "visible" }}>
      {/* grade mais clara (antes #2C2C2C, sumia no fundo escuro) */}
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1={0} x2={W} y1={(i / 3) * H} y2={(i / 3) * H} stroke="rgba(242,239,233,0.32)"
          strokeWidth={2} strokeDasharray="8 10" />
      ))}
      <line x1={0} y1={0} x2={0} y2={H} stroke="rgba(242,239,233,0.5)" strokeWidth={3} />
      <line x1={0} y1={H} x2={W} y2={H} stroke="rgba(242,239,233,0.5)" strokeWidth={3} />
      {/* área sob a linha: revela junto com o traço */}
      <path d={`${d} L ${W} ${H} L 0 ${H} Z`} fill="rgba(61,220,132,0.16)"
        style={{ clipPath: `inset(0 ${100 - linha * 100}% 0 0)` }} />
      <path d={d} fill="none" stroke={color.green} strokeWidth={8} strokeLinejoin="round" pathLength={1}
        strokeDasharray={1} strokeDashoffset={1 - linha} />
      <text x={0} y={H + 50} fill="#C9C4BC" fontFamily={font.mono} fontSize={28}>INÍCIO</text>
      <text x={W} y={H + 50} fill="#C9C4BC" fontFamily={font.mono} fontSize={28} textAnchor="end">
        FINAL DE CARREIRA
      </text>
    </svg>
  );
  const onzeMil = (top: number) => (
    <div style={{ position: "absolute", top, right: 0, textAlign: "right", ...appear(frame, t(38.5)) }}>
      <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: 76, color: color.green }}>≈ R$ 11 mil</div>
      <div style={{ fontFamily: font.mono, fontSize: 24, color: color.muted }}>CARREIRA FEDERAL</div>
    </div>
  );
  const estabilidade = (
    <div style={{
      display: "inline-block", padding: "18px 34px", borderRadius: 999,
      border: `3px solid ${color.coral}`, color: color.coral, fontFamily: font.ui, fontWeight: 600,
      fontSize: pick(f, { story: 44, feed: 40, h: 46 }), ...appear(frame, t(40.9)),
    }}>
      ✓ Estabilidade garantida por lei
    </div>
  );

  if (f === "h") {
    // duas colunas: número à esquerda, gráfico à direita; selo centralizado embaixo
    return (
      <Cutaway durationInFrames={dur} background={darkBg}>
        <div style={{ position: "absolute", top: 230, left: 140, width: 800, color: color.text }}>
          {kicker}
          {numero}
        </div>
        <div style={{ position: "absolute", top: 150, left: 980, width: W, color: color.text }}>
          <div style={{ position: "relative", height: 130 }}>{onzeMil(0)}</div>
          {grafico}
        </div>
        <div style={{ position: "absolute", top: 735, left: 0, right: 0, textAlign: "center" }}>{estabilidade}</div>
      </Cutaway>
    );
  }

  return (
    <Cutaway durationInFrames={dur} background={darkBg}>
      <div style={{ position: "absolute", top: pick(f, { story: 200, feed: 50, h: 0 }), left: 100, width: 880, color: color.text }}>
        {kicker}
        {numero}
        <div style={{ marginTop: pick(f, { story: 30, feed: 16, h: 0 }) }}>{grafico}</div>
        {onzeMil(pick(f, { story: 268, feed: 214, h: 0 }))}
        {/* bloco vai de x=100 a 980: centro dele = centro do canvas (540) */}
        <div style={{ marginTop: pick(f, { story: 40, feed: 22, h: 0 }), textAlign: "center" }}>{estabilidade}</div>
      </div>
    </Cutaway>
  );
};

/* 3 · Carimbo: status do concurso ------------------------------------------- */
export const StatusCarimbo: React.FC<P> = ({ start, dur }) => {
  const t = useAt(start);
  const f = useFormato();
  return (
    <Cutaway durationInFrames={dur} background={darkBg}>
      <Sheet tilt={3} width={pick(f, { story: 900, feed: 900, h: 1320 })} top={pick(f, { story: 190, feed: 50, h: 90 })}>
        <Kicker>Concurso INSS · situação hoje</Kicker>
        <div style={{ display: f === "h" ? "flex" : "block", alignItems: "center", gap: 60 }}>
          <div style={{ fontFamily: font.serif, fontWeight: 700, fontSize: pick(f, { story: 96, feed: 84, h: 96 }), lineHeight: 1.05,
            whiteSpace: f === "h" ? "nowrap" : "normal" }}>
            O edital já saiu?
          </div>
          <div style={{ margin: pick(f, { story: "40px 0 30px", feed: "26px 0 20px", h: "0" }) }}>
            <Stamp from={t(46.1)} style={{ fontSize: pick(f, { story: 92, feed: 78, h: 92 }), whiteSpace: "nowrap" }}>AINDA NÃO</Stamp>
          </div>
        </div>
        <div style={{ fontFamily: font.serif, fontSize: pick(f, { story: 48, feed: 42, h: 50 }), lineHeight: 1.35,
          marginTop: f === "h" ? 36 : 0 }}>
          Está{" "}
          <Marker at={47.4} startSec={start}>
            aguardando autorização
          </Marker>{" "}
          para um novo concurso.
        </div>
        <Handwriting from={t(49.6)} style={{ marginTop: pick(f, { story: 30, feed: 16, h: 24 }), fontSize: pick(f, { story: 64, feed: 54, h: 64 }) }}>
          → dá tempo de se preparar!
        </Handwriting>
      </Sheet>
    </Cutaway>
  );
};

/* 4 · Rota no mapa: 2h por dia, médio e longo prazo ------------------------- */
/*
 * Fundo: ilustração do Gemini (public/mapa-montanha-limpo.jpg, 1536×2752) em 1080×1935,
 * 7 px cortados em cima — as coordenadas abaixo estão no canvas 1080×1920 do story.
 * Em feed/h o mesmo bloco 1080×1920 é reduzido (0,5625) para o painel da direita.
 * ESTRADA segue a estrada pintada até o campo ao pé da montanha;
 * TRILHA sobe em zigue-zague pela face iluminada da montanha grande até o cume.
 */
const ESTRADA = [
  [120, 1840], [200, 1790], [245, 1750], [245, 1680], [225, 1600], [205, 1520], [215, 1480], [280, 1445],
  [380, 1410], [450, 1390], [455, 1350], [430, 1280], [405, 1220], [410, 1180], [480, 1150], [580, 1120],
  [615, 1090], [600, 1040], [575, 1000], [560, 968],
].map(([x, y], i) => `${i ? "L" : "M"} ${x} ${y}`).join(" ");
const TRILHA =
  "M 560 968 L 505 935 L 420 880 L 470 820 L 400 760 L 452 690 L 425 620 L 470 545 L 478 405";
const CUME = { x: 478, y: 402 };

/** Ilustração + rota + bandeira em coordenadas 1080×1920 (escala junto com o painel). */
const MapaDesenhado: React.FC<{ p: number; trilha: number; flag: number; zoom: number; rotulo: boolean }> = ({
  p, trilha, flag, zoom, rotulo,
}) => {
  const traco = { fill: "none", strokeLinecap: "round", strokeLinejoin: "round", pathLength: 1, strokeDasharray: 1 } as const;
  return (
    <AbsoluteFill style={{ width: 1080, height: 1920, scale: zoom, transformOrigin: "50% 45%" }}>
      <Img src={staticFile("mapa-montanha-limpo.jpg")}
        style={{ position: "absolute", left: 0, top: -7, width: 1080, height: 1935 }} />
      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        {/* contorno escuro por baixo: a rota coral destaca da estrada bege */}
        <path d={ESTRADA} {...traco} stroke="rgba(17,17,17,0.55)" strokeWidth={22} strokeDashoffset={1 - p} />
        <path d={ESTRADA} {...traco} stroke={color.coral} strokeWidth={13} strokeDashoffset={1 - p} />
        <path d={TRILHA} {...traco} stroke="rgba(17,17,17,0.55)" strokeWidth={20} strokeDashoffset={1 - trilha} />
        <path d={TRILHA} {...traco} stroke={color.coral} strokeWidth={11} strokeDashoffset={1 - trilha} />
        <circle cx={120} cy={1840} r={22} fill={color.night} stroke={color.coral} strokeWidth={10} />
        {/* bandeira no cume */}
        <g style={{ opacity: flag > 0 ? 1 : 0 }}>
          <g style={{ scale: `1 ${flag}`, transformOrigin: `${CUME.x}px ${CUME.y}px`, transformBox: "view-box" }}>
            <line x1={CUME.x} y1={CUME.y} x2={CUME.x} y2={CUME.y - 150} stroke={color.text} strokeWidth={8} strokeLinecap="round" />
            <polygon points={`${CUME.x},${CUME.y - 150} ${CUME.x + 110},${CUME.y - 122} ${CUME.x},${CUME.y - 94}`} fill={color.coral} />
          </g>
        </g>
      </svg>
      {rotulo && (
        <div style={{ position: "absolute", left: CUME.x + 130, top: CUME.y - 190, ...rotuloAprovacao(flag, 54) }}>
          Aprovação
        </div>
      )}
    </AbsoluteFill>
  );
};

const rotuloAprovacao = (flag: number, size: number): React.CSSProperties => ({
  whiteSpace: "nowrap", padding: "16px 30px", borderRadius: 999, background: color.coral, color: "white",
  fontFamily: font.ui, fontWeight: 800, fontSize: size, boxShadow: "0 14px 34px rgba(0,0,0,0.35)",
  opacity: flag, scale: interpolate(flag, [0, 1], [0.6, 1]), transformOrigin: "0% 50%",
});

export const RotaMapa: React.FC<P> = ({ start, dur }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const painel = usePainel();
  const p = interpolate(frame, [t(63.3), t(68.9)], [0, 1], { ...clamp, easing: Easing.inOut(Easing.quad) });
  const trilha = interpolate(frame, [t(70.9), t(73.7)], [0, 1], { ...clamp, easing: Easing.inOut(Easing.quad) });
  // bandeira sobe no "aprovada" (73,78 s)
  const flag = interpolate(frame, [t(73.75), t(74.1)], [0, 1], { ...clamp, easing: Easing.back(2) });
  const zoom = interpolate(frame, [0, dur], [1, 1.06]);

  const titulo = (size: number, sombra: boolean) => (
    <>
      <div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: "#C9C4BC" }}>ROTA ATÉ A APROVAÇÃO</div>
      <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: size, lineHeight: 1.05, color: color.text,
        textShadow: sombra ? "0 4px 24px rgba(0,0,0,0.6)" : "none" }}>
        Preparação de{" "}
        <span style={{ color: color.coral, opacity: interpolate(frame, [t(65.4), t(65.6)], [0.25, 1], clamp) }}>
          médio e longo prazo
        </span>
      </div>
    </>
  );
  const duasHoras: React.CSSProperties = {
    padding: "20px 34px", borderRadius: 999, background: color.card,
    border: `2px solid ${color.line}`, color: color.text, fontFamily: font.ui, fontWeight: 800, fontSize: 52,
    boxShadow: "0 16px 40px rgba(0,0,0,0.5)", ...appear(frame, t(70.3)),
  };

  if (f === "story") {
    return (
      <Cutaway durationInFrames={dur} background={color.night}>
        {/* imagem + rota + bandeira no mesmo bloco: o zoom lento não desalinha nada */}
        <MapaDesenhado p={p} trilha={trilha} flag={flag} zoom={zoom} rotulo />
        <div style={{
          position: "absolute", top: 150, left: 90, right: 90, ...appear(frame, t(63.2)),
          // sai de cena quando a trilha chega ao cume, para a bandeira ser o destaque
          ...(frame > t(73.2) ? { opacity: interpolate(frame, [t(73.2), t(73.6)], [1, 0], clamp) } : {}),
        }}>
          {titulo(84, true)}
        </div>
        <div style={{ position: "absolute", top: 1000, left: 60, ...duasHoras }}>⏱ 2h por dia</div>
      </Cutaway>
    );
  }

  // feed/h: mapa inteiro no painel da direita (reduzido), título e "2h" na coluna escura
  const k = painel.h / 1920;
  return (
    <Cutaway durationInFrames={dur} background={darkBg}>
      <div style={{ position: "absolute", left: painel.x, top: 0, width: painel.w, height: painel.h, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: 1920, scale: k, transformOrigin: "0 0" }}>
          <MapaDesenhado p={p} trilha={trilha} flag={flag} zoom={zoom} rotulo={false} />
        </div>
      </div>
      <div style={{
        position: "absolute", left: pick(f, { story: 0, feed: 40, h: 150 }), top: pick(f, { story: 0, feed: 90, h: 200 }),
        width: painel.colW - pick(f, { story: 0, feed: 70, h: 300 }), ...appear(frame, t(63.2)),
      }}>
        {titulo(pick(f, { story: 84, feed: 58, h: 96 }), false)}
        <div style={{ display: "inline-block", marginTop: pick(f, { story: 0, feed: 44, h: 70 }), ...duasHoras }}>⏱ 2h por dia</div>
        {/* bandeira no cume do painel → rótulo aqui na coluna (no painel ele cortava na borda) */}
        <div style={{ marginTop: pick(f, { story: 0, feed: 34, h: 50 }) }}>
          <div style={{ display: "inline-block", ...rotuloAprovacao(flag, pick(f, { story: 54, feed: 52, h: 64 })) }}>⚑ Aprovação</div>
        </div>
      </div>
    </Cutaway>
  );
};

/* 5 · Papel na mesa: sem método × com método ------------------------------- */
export const MetodoMesa: React.FC<P> = ({ start, dur }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  // gráfico desenhado em 780×420 e escalado por formato (mantém o círculo redondo)
  const W = 780, H = 420;
  const k = pick(f, { story: 1, feed: 0.72, h: 0.84 });
  const semMetodo = "M 0 330 C 80 300, 140 340, 220 310 S 380 330, 460 300 S 640 320, 780 300";
  const comMetodo = "M 0 340 C 160 320, 280 260, 420 190 S 660 60, 780 30";
  const draw = (a: number, b: number) => interpolate(frame, [t(a), t(b)], [1, 0], { ...clamp, easing: ease });
  const tape: React.CSSProperties = { position: "absolute", width: 170, height: 52, background: "rgba(235,225,200,0.75)" };

  return (
    <Cutaway
      durationInFrames={dur}
      background={`repeating-linear-gradient(0deg, transparent 0 59px, rgba(255,255,255,0.12) 59px 61px),
        repeating-linear-gradient(90deg, transparent 0 59px, rgba(255,255,255,0.12) 59px 61px), ${color.mat}`}
    >
      <Sheet tilt={-2} width={pick(f, { story: 900, feed: 900, h: 1360 })} top={pick(f, { story: 210, feed: 40, h: 50 })}>
        <div style={{ ...tape, top: -26, left: pick(f, { story: 340, feed: 340, h: 500 }), rotate: "-4deg" }} />
        <Kicker>Por que tanta gente estuda e não passa</Kicker>
        <div style={{ fontFamily: font.serif, fontWeight: 700, fontSize: pick(f, { story: 64, feed: 52, h: 56 }), lineHeight: 1.1,
          marginBottom: pick(f, { story: 30, feed: 18, h: 24 }) }}>
          Mesmas 2h por dia, resultados opostos
        </div>
        <svg width={W * k} height={H * k} viewBox={`0 0 ${W} ${H}`} style={{ overflow: "visible", display: "block",
          marginLeft: f === "h" ? 220 : 0 }}>
          <line x1={0} y1={H} x2={W} y2={H} stroke={color.ink} strokeWidth={3} />
          <line x1={0} y1={0} x2={0} y2={H} stroke={color.ink} strokeWidth={3} />
          <path d={semMetodo} fill="none" stroke="#9A948A" strokeWidth={7} pathLength={1} strokeDasharray={1}
            strokeDashoffset={draw(86.2, 87.8)} />
          <path d={comMetodo} fill="none" stroke={color.ink} strokeWidth={8} pathLength={1} strokeDasharray={1}
            strokeDashoffset={draw(89.7, 91.0)} />
          <text x={W} y={360} textAnchor="end" fontFamily={font.mono} fontSize={26 / Math.min(k, 1)} fill="#7A746A"
            opacity={interpolate(frame, [t(87.0), t(87.4)], [0, 1], clamp)}>sem método</text>
          <text x={430} y={150} fontFamily={font.mono} fontSize={26 / Math.min(k, 1)} fill={color.ink}
            opacity={interpolate(frame, [t(90.1), t(90.5)], [0, 1], clamp)}>método certo</text>
          {/* círculo vermelho feito à mão em volta do topo da curva */}
          <path d="M 700 -10 C 790 -40, 860 30, 800 80 C 740 120, 640 80, 660 20 C 670 -10, 720 -30, 760 -25"
            fill="none" stroke={color.marker} strokeWidth={7} strokeLinecap="round" pathLength={1}
            opacity={frame >= t(91.7) ? 1 : 0}
            strokeDasharray={1} strokeDashoffset={draw(91.7, 92.3)} />
        </svg>
        <Handwriting from={t(91.9)} style={{ textAlign: "right", marginTop: 10, fontSize: pick(f, { story: 64, feed: 52, h: 60 }) }}>
          evolui mais rápido
        </Handwriting>
      </Sheet>
      <div
        style={{
          position: "absolute", top: pick(f, { story: 1010, feed: 610, h: 600 }), left: pick(f, { story: 70, feed: 24, h: 40 }),
          rotate: "-6deg", background: "#F7F3EA", padding: "10px 26px",
          fontFamily: font.stamp, fontSize: pick(f, { story: 88, feed: 70, h: 84 }), color: color.ink,
          boxShadow: "0 12px 30px rgba(0,0,0,0.35)", ...appear(frame, t(89.5)),
        }}
      >
        <div style={{ ...tape, top: -22, left: 20, width: 110, rotate: "8deg" }} />
        O MÉTODO
      </div>
    </Cutaway>
  );
};

/* 6 · Cartão do curso ------------------------------------------------------- */
export const ProjetoCard: React.FC<P> = ({ start, dur }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const { width } = useVideoConfig();
  const cardW = pick(f, { story: 900, feed: 900, h: 1360 });
  return (
    <Cutaway durationInFrames={dur} background={darkBg}>
      <div style={{
        position: "absolute", top: pick(f, { story: 300, feed: 110, h: 170 }), left: (width - cardW) / 2, width: cardW,
        padding: pick(f, { story: 64, feed: 56, h: 72 }), borderRadius: 40, background: color.card,
        border: `2px solid ${color.line}`, color: color.text, boxSizing: "border-box",
      }}>
        <div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.coral }}>✳ CURSO DO MATEUS</div>
        <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 150, feed: 130, h: 170 }), letterSpacing: -5,
          lineHeight: 1, marginTop: 24 }}>
          Projeto{f === "h" ? " " : <br />}INSS
        </div>
        <div style={{ fontFamily: font.ui, fontSize: pick(f, { story: 46, feed: 42, h: 50 }), color: color.muted, marginTop: 26,
          ...appear(frame, t(104.6)) }}>
          Como estudar para ser aprovada
        </div>
        <div style={{ position: "absolute", right: 60, top: pick(f, { story: 200, feed: 170, h: 250 }) }}>
          <Stamp from={t(103.3)} rotate={-12} style={{ color: color.lime, borderColor: color.lime, mixBlendMode: "normal",
            fontSize: pick(f, { story: 92, feed: 80, h: 96 }) }}>
            GRATUITO
          </Stamp>
        </div>
      </div>
    </Cutaway>
  );
};

/* 7 · Checklist do que se aprende ------------------------------------------ */
const ITENS: [number, string][] = [
  [110.9, "Como organizar as matérias"],
  [112.0, "Quanto tempo estudar cada uma"],
  [114.5, "As matérias mais importantes"],
  [117.1, "O Método Ativo 5x"],
];

export const ChecklistCurso: React.FC<P> = ({ start, dur }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const size = pick(f, { story: 48, feed: 40, h: 44 });
  return (
    <Cutaway durationInFrames={dur} background={darkBg}>
      <div style={{
        position: "absolute", top: pick(f, { story: 220, feed: 60, h: 120 }),
        left: pick(f, { story: 90, feed: 90, h: 150 }), right: pick(f, { story: 90, feed: 90, h: 150 }), color: color.text,
      }}>
        <div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.muted }}>NO PROJETO INSS</div>
        <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 84, feed: 66, h: 84 }), lineHeight: 1.05,
          margin: pick(f, { story: "16px 0 50px", feed: "12px 0 30px", h: "14px 0 44px" }) }}>
          Você vai aprender
        </div>
        {/* h: grade 2×2; story/feed: lista */}
        <div style={{ display: f === "h" ? "grid" : "block", gridTemplateColumns: "1fr 1fr", columnGap: 28 }}>
          {ITENS.map(([at, txt], i) => {
            const last = i === ITENS.length - 1;
            const on = interpolate(frame, [t(at), t(at) + 8], [0, 1], clamp);
            return (
              <div key={txt} style={{
                display: "flex", alignItems: "center", gap: pick(f, { story: 30, feed: 24, h: 28 }),
                padding: pick(f, { story: "30px 34px", feed: "22px 28px", h: "30px 34px" }),
                marginBottom: pick(f, { story: 22, feed: 16, h: 24 }), borderRadius: 26,
                background: last ? color.coral : color.card, border: `2px solid ${last ? color.coral : color.line}`,
                fontFamily: font.ui, fontWeight: last ? 800 : 600, fontSize: size, ...appear(frame, t(at)),
              }}>
                <div style={{
                  width: size * 1.25, height: size * 1.25, flexShrink: 0, borderRadius: 999, display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: size * 0.75, background: last ? "white" : color.lime,
                  color: last ? color.coral : color.ink, scale: interpolate(on, [0, 1], [0.3, 1]),
                }}>✓</div>
                {txt}
              </div>
            );
          })}
        </div>
      </div>
    </Cutaway>
  );
};

/* 8 · Contador de aprovações ----------------------------------------------- */
export const Aprovacoes: React.FC<P> = ({ start, dur }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const n = Math.round(interpolate(frame, [t(120.4), t(121.2)], [0, 6], clamp));
  const medalha = pick(f, { story: 150, feed: 124, h: 150 });
  const medalhas = (
    <div style={{ display: "flex", alignItems: "center", gap: 26, ...appear(frame, t(122.3)) }}>
      {[0, 1].map((k) => (
        <div key={k} style={{
          width: medalha, height: medalha, borderRadius: 999, background: "#E9B949", color: color.ink, display: "flex",
          alignItems: "center", justifyContent: "center", fontFamily: font.ui, fontWeight: 800, fontSize: medalha * 0.43,
          boxShadow: "inset 0 -10px 0 rgba(0,0,0,0.18)",
          scale: interpolate(frame, [t(122.3) + k * 4, t(122.3) + k * 4 + 10], [0.4, 1], { ...clamp, easing: Easing.back(2) }),
        }}>1º</div>
      ))}
      <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 64, feed: 56, h: 64 }) }}>duas em<br />1º lugar</div>
    </div>
  );
  return (
    <Cutaway durationInFrames={dur} background={darkBg}>
      <div style={{
        position: "absolute", top: pick(f, { story: 230, feed: 70, h: 190 }),
        left: pick(f, { story: 90, feed: 90, h: 170 }), right: pick(f, { story: 90, feed: 90, h: 170 }), color: color.text,
      }}>
        <div style={{ fontFamily: font.mono, fontSize: 26, letterSpacing: 3, color: color.muted }}>
          RESULTADO DO MÉTODO ATIVO 5X
        </div>
        {/* h: número + texto à esquerda, medalhas à direita na mesma linha */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: f === "h" ? "nowrap" : "wrap" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 30 }}>
            <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 380, feed: 300, h: 380 }), letterSpacing: -14, lineHeight: 1 }}>{n}</div>
            <div style={{ fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 72, feed: 62, h: 76 }), lineHeight: 1.05 }}>aprovações<br />em concurso</div>
          </div>
          <div style={{ marginTop: f === "h" ? 0 : pick(f, { story: 40, feed: 24, h: 0 }), width: f === "h" ? "auto" : "100%" }}>{medalhas}</div>
        </div>
      </div>
    </Cutaway>
  );
};

/* CTA (por cima do vídeo, sem esconder o Mateus) ---------------------------- */
export const CtaFinal: React.FC<P> = ({ start }) => {
  const frame = useCurrentFrame();
  const t = useAt(start);
  const f = useFormato();
  const bob = Math.sin(frame / 6) * 8;
  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      {/* botão na parte de baixo (pedido 11/11); a legenda sobe nesse trecho (Captions.tsx).
          feed/h: acima da legenda queimada do bruto (y≈855–970) */}
      <div style={{
        position: "absolute", top: pick(f, { story: 1480, feed: 636, h: 600 }), padding: "26px 44px", borderRadius: 30,
        background: color.coral, color: "white", fontFamily: font.ui, fontWeight: 800, fontSize: pick(f, { story: 56, feed: 50, h: 54 }),
        textAlign: "center", boxShadow: "0 20px 50px rgba(0,0,0,0.4)", ...appear(frame, 0),
      }}>
        Cadastro gratuito
        <div style={{ fontWeight: 600, fontSize: pick(f, { story: 38, feed: 34, h: 36 }), opacity: 0.9 }}>Projeto INSS · grupo no WhatsApp</div>
      </div>
      <div style={{
        position: "absolute", top: pick(f, { story: 1680, feed: 790, h: 752 }), fontFamily: font.ui, fontWeight: 800,
        fontSize: pick(f, { story: 48, feed: 40, h: 42 }), color: "white",
        textShadow: "0 4px 20px rgba(0,0,0,0.6)", translate: `0px ${bob}px`, ...{ opacity: appear(frame, t(135.6)).opacity },
      }}>
        toque no botão ↓
      </div>
    </AbsoluteFill>
  );
};
