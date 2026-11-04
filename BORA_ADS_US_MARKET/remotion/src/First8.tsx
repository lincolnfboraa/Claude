import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, CATALOG, Catalog, DotGrid, FONT, PhoneFrame, SCREEN, fill} from './brand';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const eOut = Easing.out(Easing.cubic);
const eInOut = Easing.inOut(Easing.cubic);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/* ================= 0–1,5s | MONTAGEM (7 takes, cortes nas colcheias) ================= */

// Foto de produto em tela cheia. (ox, oy) = ponto da imagem que fica no centro da tela.
const Photo: React.FC<{ox: number; oy: number; s: [number, number]; r?: [number, number]; dx?: [number, number]; d: number}> = ({
  ox, oy, s, r = [0, 0], dx = [0, 0], d,
}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, d], [0, 1], {...clamp, easing: eOut});
  const size = 1920;
  const sc = lerp(s[0], s[1], t);
  return (
    <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
      <Img src={staticFile('truffles.jpg')} style={{position: 'absolute', width: size, height: size, left: 540 - ox * size, top: 960 - oy * size,
        transformOrigin: `${ox * 100}% ${oy * 100}%`, transform: `translateX(${lerp(dx[0], dx[1], t)}px) scale(${sc}) rotate(${lerp(r[0], r[1], t)}deg)`}} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 45%, rgba(10,4,0,.55) 100%)'}} />
    </AbsoluteFill>
  );
};

// Interface real em tela cheia, mesma lógica de enquadramento
const UIShot: React.FC<{cx: [number, number]; cy: [number, number]; s: [number, number]; d: number; e?: (t: number) => number}> = ({cx, cy, s, d, e = eOut}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, d], [0, 1], {...clamp, easing: e});
  const sc = lerp(s[0], s[1], t), x = lerp(cx[0], cx[1], t), y = lerp(cy[0], cy[1], t);
  return (
    <AbsoluteFill style={{background: C.beige, overflow: 'hidden'}}>
      <Img src={staticFile(CATALOG.src)} style={{position: 'absolute', left: 0, top: 0, width: CATALOG.w, height: CATALOG.h,
        transformOrigin: '0 0', transform: `translate(${540 - x * sc}px, ${960 - y * sc}px) scale(${sc})`}} />
    </AbsoluteFill>
  );
};

// pontos no print do catálogo
const TRUFA = {x: 588, y: 1269}, BOMBOM = {x: 996, y: 1269}, HEADER = {x: 660, y: 330};

const Montage = () => (
  <>
    {/* T1 plano geral das trufas, speed ramp */}
    <Sequence durationInFrames={7}><Photo ox={0.5} oy={0.5} s={[1.35, 1.08]} d={7} /></Sequence>
    {/* T2 detalhe da folha de ouro, movimento contrário */}
    <Sequence from={7} durationInFrames={5}><Photo ox={0.47} oy={0.26} s={[2.0, 2.25]} dx={[60, -40]} d={5} /></Sequence>
    {/* T3 macro da trufa partida */}
    <Sequence from={12} durationInFrames={6}><Photo ox={0.6} oy={0.56} s={[2.1, 1.85]} r={[-3, 0]} d={6} /></Sequence>
    {/* T4 match cut: a trufa vira o card "Trufa Tradicional" no catálogo */}
    <Sequence from={18} durationInFrames={6}><UIShot cx={[TRUFA.x, TRUFA.x]} cy={[TRUFA.y, TRUFA.y]} s={[4.2, 3.0]} d={6} /></Sequence>
    {/* T5 swipe lateral até o bombom de morango */}
    <Sequence from={24} durationInFrames={6}><UIShot cx={[TRUFA.x + 140, BOMBOM.x]} cy={[TRUFA.y, BOMBOM.y]} s={[2.6, 2.6]} d={6} e={eInOut} /></Sequence>
    {/* T6 marca do cliente no topo do catálogo */}
    <Sequence from={30} durationInFrames={6}><UIShot cx={[HEADER.x, HEADER.x]} cy={[HEADER.y + 60, HEADER.y]} s={[2.0, 2.3]} d={6} /></Sequence>
    {/* T7 abre para o catálogo inteiro */}
    <Sequence from={36} durationInFrames={9}><UIShot cx={[660, 660]} cy={[1000, 1150]} s={[1.5, 0.82]} d={9} /></Sequence>
  </>
);

/* ================= 1,5–2,5s | LOGO ================= */
const Logo = () => {
  const f = useCurrentFrame();
  const reveal = interpolate(f, [0, 9], [100, 0], {...clamp, easing: eOut});
  const s = interpolate(f, [0, 22], [1.07, 1], {...clamp, easing: eOut});
  const outT = interpolate(f, [24, 30], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const sheen = interpolate(f, [4, 20], [-40, 140], clamp);
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 50% 50%, #0d3a5c, ${C.navy} 60%)`, alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'relative', width: 760, height: 292, transform: `scale(${s * (1 - 0.05 * outT)})`, opacity: 1 - outT,
        clipPath: `inset(0 ${reveal}% 0 0)`}}>
        <Img src={staticFile('bora_logo.png')} style={{width: 760}} />
        <div style={{...fill, mixBlendMode: 'overlay',
          background: `linear-gradient(105deg, transparent ${sheen - 20}%, rgba(255,255,255,.55) ${sheen}%, transparent ${sheen + 20}%)`}} />
      </div>
    </AbsoluteFill>
  );
};

/* ================= 2,5–6s | GANCHO + MENSAGENS QUE VIRAM A TELA ================= */
const msgs = [
  {t: 5, x: 80, y: 690, text: 'How much is this?'},
  {t: 14, x: 150, y: 830, text: 'Do you have a menu?'},
  {t: 22, x: 90, y: 970, text: 'What flavors are available?'},
  {t: 29, x: 170, y: 1110, text: 'Do you deliver this weekend?'},
  {t: 35, x: 110, y: 1250, text: 'Price for 50 truffles?'},
  {t: 40, x: 190, y: 1390, text: 'Can you send me the full list?'},
].map((m) => ({...m, w: Math.min(840, 112 + m.text.length * 21.5), h: 104}));

// frames locais (0 = 2,5s)
const MERGE_START = 63, MERGE_END = 87, FRAME_IN = 81, SCREEN_ON = 85;

const HookAndMerge = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const headIn = (line: number) => interpolate(f, [1 + line * 3, 11 + line * 3], [1, 0], {...clamp, easing: eOut});
  const headOut = interpolate(f, [56, 66], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const press = f > 42 && f < 56 ? Math.sin(f * 2.4) * interpolate(f, [42, 56], [5, 0]) : 0;
  const frameIn = interpolate(f, [FRAME_IN, FRAME_IN + 10], [0, 1], {...clamp, easing: eOut});
  const wipe = interpolate(f, [SCREEN_ON, SCREEN_ON + 14], [100, 0], {...clamp, easing: eInOut});
  const lines: React.ReactNode[] = [
    <>Your customers</>,
    <>shouldn't have to</>,
    <><span style={{color: C.orange}}>DM you</span> just to</>,
    <>see your products.</>,
  ];
  return (
    <AbsoluteFill>
      {/* headline aparece uma vez e sai antes da transição */}
      <div style={{position: 'absolute', left: 80, right: 60, top: 200, font: `800 80px/1.06 ${FONT}`, letterSpacing: -2.5, color: '#fff',
        opacity: 1 - headOut, transform: `translateY(${-headOut * 70}px)`}}>
        {lines.map((l, i) => (
          <div key={i} style={{overflow: 'hidden'}}>
            <div style={{transform: `translateY(${headIn(i) * 105}%)`}}>{l}</div>
          </div>
        ))}
      </div>

      {/* celular entra em volta das mensagens já fundidas */}
      <PhoneFrame style={{opacity: frameIn, transform: `scale(${1.04 - 0.04 * frameIn})`}}>
        <div style={{...fill, clipPath: `inset(0 0 ${wipe}% 0)`}}><Catalog /></div>
      </PhoneFrame>

      {/* mensagens: aparecem, acumulam e se fundem na tela do celular */}
      {msgs.map((m, i) => {
        if (f < m.t) return null;
        const pop = spring({frame: f - m.t, fps, config: {damping: 15, stiffness: 340}});
        const k = interpolate(f, [MERGE_START + i * 1.5, MERGE_END - 6 + i * 1.5], [0, 1], {...clamp, easing: eInOut});
        const gone = interpolate(f, [SCREEN_ON, SCREEN_ON + 4], [1, 0], clamp);
        const x = lerp(m.x + press, SCREEN.x, k), y = lerp(m.y, SCREEN.y, k);
        const w = lerp(m.w, SCREEN.w, k), h = lerp(m.h, SCREEN.h, k);
        return (
          <div key={i} style={{position: 'absolute', left: x, top: y, width: w, height: h, borderRadius: lerp(52, SCREEN.r, k),
            borderBottomLeftRadius: lerp(12, SCREEN.r, k), background: C.beige, opacity: Math.min(1, pop * 1.6) * gone,
            boxShadow: `0 ${lerp(16, 0, k)}px ${lerp(40, 0, k)}px rgba(0,0,0,.35)`,
            transform: `scale(${lerp(pop, 1, k)})`, transformOrigin: 'left bottom', overflow: 'hidden'}}>
            <div style={{position: 'absolute', left: 34, top: 0, height: 104, display: 'flex', alignItems: 'center', gap: 18, whiteSpace: 'nowrap',
              font: `500 42px ${FONT}`, color: C.navy, opacity: 1 - Math.min(1, k * 3)}}>
              <span style={{width: 14, height: 14, borderRadius: 7, background: C.orange}} />
              {m.text}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* ================= 6–8s | REVEAL PREMIUM ================= */
const RevealLayer = () => {
  const f = useCurrentFrame(); // 0 = 6s
  const push = interpolate(f, [0, 60], [1, 1.06], {...clamp, easing: Easing.out(Easing.quad)});
  const lift = interpolate(f, [0, 60], [0, -30], {...clamp, easing: Easing.out(Easing.quad)});
  const scroll = interpolate(f, [14, 60], [0, 40], {...clamp, easing: eInOut});
  const head = interpolate(f, [6, 18], [1, 0], {...clamp, easing: eOut});
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 80, right: 80, top: 210, font: `800 80px/1.06 ${FONT}`, letterSpacing: -2.5, color: '#fff'}}>
        {[<>Give them a <span style={{color: C.orange}}>better way</span></>, <>to shop.</>].map((l, i) => (
          <div key={i} style={{overflow: 'hidden'}}>
            <div style={{transform: `translateY(${interpolate(f, [6 + i * 3, 18 + i * 3], [105, 0], {...clamp, easing: eOut})}%)`, opacity: 1 - head * 0.3}}>{l}</div>
          </div>
        ))}
      </div>
      <AbsoluteFill style={{transform: `translateY(${lift}px) scale(${push})`, transformOrigin: '50% 62%'}}>
        <PhoneFrame><Catalog scroll={scroll} /></PhoneFrame>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ================= composição ================= */
const NavyStage = () => {
  const f = useCurrentFrame(); // 0 = 2,5s
  const glow = interpolate(f, [80, 110], [0, 1], clamp);
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 50% 35%, #0d3a5c, ${C.navy} 55%, ${C.deep} 100%)`}}>
      <DotGrid opacity={0.22} />
      <AbsoluteFill style={{opacity: glow * 0.55, background: `radial-gradient(ellipse 45% 35% at 50% 62%, ${C.orange}, transparent 70%)`}} />
    </AbsoluteFill>
  );
};

export const First8: React.FC = () => (
  <AbsoluteFill style={{background: '#000', fontFamily: FONT}}>
    <Montage />
    <Sequence from={45} durationInFrames={30}><Logo /></Sequence>
    <Sequence from={75}>
      <NavyStage />
      <Sequence durationInFrames={105}><HookAndMerge /></Sequence>
      <Sequence from={105}><RevealLayer /></Sequence>
    </Sequence>
    <Audio src={staticFile('score_v2.wav')} />
  </AbsoluteFill>
);
