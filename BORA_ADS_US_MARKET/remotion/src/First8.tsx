import React from 'react';
import {
  AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';
import {C, Catalog, DotGrid, FONT, Phone, Placeholder, SelectionBox, fill} from './brand';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const out = Easing.out(Easing.cubic);

/* ---------- CENA 01 | 0–3s | sem locução ---------- */

// A: macro chocolate, speed ramp (entra rápido e desacelera)
const FrameA = () => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, 12], [1.4, 1.16], {...clamp, easing: out});
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <Img src={staticFile('truffles.jpg')} style={{...fill, width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${s})`}} />
    </AbsoluteFill>
  );
};

// B: mão posicionando doce (ainda sem B-roll, usa punch-in no macro)
const FrameB: React.FC<{ph: boolean}> = ({ph}) => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, 12], [2.6, 2.3], {...clamp, easing: out});
  const r = interpolate(f, [0, 12], [-4, 0], clamp);
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <Img src={staticFile('truffles.jpg')} style={{...fill, width: '100%', height: '100%', objectFit: 'cover',
        transformOrigin: '50% 60%', transform: `scale(${s}) rotate(${r}deg)`}} />
      <Placeholder show={ph} label="B02 mão posicionando doce" />
    </AbsoluteFill>
  );
};

// C: celular com o catálogo
const FrameC: React.FC<{ph: boolean}> = ({ph}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: f, fps, config: {damping: 18, stiffness: 180}});
  return (
    <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 40%, #3b2316, #120a06 70%)', alignItems: 'center', justifyContent: 'center'}}>
      <Phone style={{transform: `translateY(${(1 - p) * 500}px) rotate(${(1 - p) * -6}deg)`}}>
        <Catalog scroll={interpolate(f, [0, 15], [0, 120], clamp)} />
      </Phone>
      <Placeholder show={ph} label="B03 mão segurando celular" />
    </AbsoluteFill>
  );
};

// D: cards de produto em grid (Transition 07)
const products = [
  {img: 'p_brigadeiro.png', name: 'Brigadeiro'},
  {img: 'p_trufa.png', name: 'Classic Truffle'},
  {img: 'p_bombom.png', name: 'Strawberry Bonbon'},
  {img: 'truffles.jpg', name: 'Gold Truffle'},
];
const FrameD = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const collapse = interpolate(f, [12, 18], [1, 0], {...clamp, easing: Easing.in(Easing.cubic)});
  return (
    <AbsoluteFill style={{background: C.deep}}>
      <DotGrid opacity={0.35} />
      {products.map((p, i) => {
        const col = i % 2, row = Math.floor(i / 2);
        const tx = (col - 0.5) * 440, ty = (row - 0.5) * 520;
        const s = spring({frame: f - i * 2, fps, config: {damping: 15, stiffness: 220}});
        return (
          <div key={p.name} style={{position: 'absolute', left: 540 - 190, top: 960 - 230, width: 380, height: 460,
            borderRadius: 36, background: C.beige, boxShadow: '0 30px 60px rgba(0,0,0,.35)',
            transform: `translate(${tx * s * collapse}px, ${ty * s * collapse}px) scale(${s * (0.4 + 0.6 * collapse)}) rotate(${(1 - s) * (i % 2 ? 8 : -8)}deg)`,
            display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 34}}>
            <Img src={staticFile(p.img)} style={{width: 290, height: 290, borderRadius: '50%', objectFit: 'cover', border: '6px solid #fff'}} />
            <div style={{font: `700 34px ${FONT}`, color: C.navy, marginTop: 30}}>{p.name}</div>
            <div style={{width: 60, height: 6, borderRadius: 3, background: C.orange, marginTop: 18}} />
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// E + F + G: navy, caixa laranja se desenha, símbolo Bora (0,3s), corte para o problema
const FrameEF = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const logo = spring({frame: f - 15, fps, config: {damping: 12, stiffness: 300}});
  const wipe = interpolate(f, [27, 33], [1920, 0], {...clamp, easing: Easing.in(Easing.cubic)});
  return (
    <AbsoluteFill style={{background: C.navy}}>
      <DotGrid />
      <SelectionBox x={540 - 300} y={960 - 210} w={600} h={420} start={0} dur={11} />
      <Img src={staticFile('bora_symbol.png')} style={{position: 'absolute', left: 540 - 125, top: 960 - 166, width: 250,
        transform: `scale(${logo})`, opacity: logo}} />
      <div style={{position: 'absolute', left: 0, right: 0, top: wipe, height: 1920, background: C.orange}} />
    </AbsoluteFill>
  );
};

/* ---------- CENA 02 | 3–7s | THE PROBLEM ---------- */

const msgs: [number, string][] = [
  [6, 'How much is this?'],
  [24, 'Do you have a menu?'],
  [40, 'What flavors are available?'],
  [52, 'Do you deliver this weekend?'],
  [61, 'Price for 50 truffles?'],
  [68, 'Is the strawberry one still available?'],
  [73, 'Can you send the full list?'],
  [77, 'Hello??'],
];

const Headline: React.FC<{start: number; parts: [string, boolean][]; top?: number; color: string}> = ({start, parts, top = 200, color}) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [start, start + 9], [0, 1], {...clamp, easing: out});
  return (
    <div style={{position: 'absolute', left: 80, right: 80, top, font: `800 76px/1.08 ${FONT}`, letterSpacing: -2, color,
      opacity: p, transform: `translateY(${(1 - p) * 40}px)`}}>
      {parts.map(([t, hi], i) => <span key={i} style={{color: hi ? C.orange : undefined}}>{t}</span>)}
    </div>
  );
};

const Problem = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const shake = f > 76 && f < 92 ? Math.sin(f * 2.2) * interpolate(f, [76, 92], [9, 0]) : 0;
  return (
    <AbsoluteFill style={{background: C.beige}}>
      <Headline start={0} color={C.navy} parts={[["Your customers shouldn't have to ", false], ['DM you', true], [' just to see your products.', false]]} />
      <div style={{position: 'absolute', left: 80, right: 80, bottom: 220, top: 640, display: 'flex', flexDirection: 'column',
        justifyContent: 'flex-end', gap: 22, transform: `translateX(${shake}px)`, overflow: 'hidden'}}>
        {msgs.filter(([t]) => f >= t).map(([t, m], i) => {
          const p = spring({frame: f - t, fps, config: {damping: 16, stiffness: 320}});
          return (
            <div key={m} style={{alignSelf: 'flex-start', maxWidth: 760, padding: '26px 34px', borderRadius: 34, borderBottomLeftRadius: 8,
              background: '#fff', color: C.navy, font: `500 42px ${FONT}`, boxShadow: '0 12px 30px rgba(7,39,64,.12)',
              transform: `scale(${p}) translateY(${(1 - p) * 30}px)`, transformOrigin: 'left bottom', opacity: Math.min(1, p * 1.5),
              display: 'flex', alignItems: 'center', gap: 18}}>
              <span style={{width: 14, height: 14, borderRadius: 7, background: i < 3 ? C.orange : '#c9bfb2', flex: 'none'}} />
              {m}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ---------- CENA 03 (início) | 7s+ | THE PRODUCT REVEAL ---------- */

const Reveal = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: f - 4, fps, config: {damping: 20, stiffness: 120}});
  const mask = interpolate(f, [10, 28], [100, 0], {...clamp, easing: Easing.inOut(Easing.cubic)});
  const push = interpolate(f, [0, 44], [0.86, 0.96], clamp);
  return (
    <AbsoluteFill style={{background: C.navy}}>
      <DotGrid />
      <Headline start={18} top={170} color="#fff" parts={[['Give them a ', false], ['better way', true], [' to shop.', false]]} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-end', paddingBottom: 0}}>
        <div style={{transform: `translateY(${(1 - p) * 260 + 140}px) scale(${push})`, transformOrigin: '50% 100%'}}>
          <Phone width={640}>
            <div style={{...fill, clipPath: `inset(${mask}% 0 0 0)`}}><Catalog /></div>
            <div style={{...fill, background: C.deep, clipPath: `inset(0 0 ${100 - mask}% 0)`}} />
          </Phone>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ---------- Problem > Reveal: Swipe World ---------- */
const SwipeWorld = () => {
  const f = useCurrentFrame(); // local, 0 = frame 90
  const x = interpolate(f, [106, 120], [0, -1080], {...clamp, easing: Easing.inOut(Easing.cubic)});
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{transform: `translateX(${x}px)`}}><Problem /></AbsoluteFill>
      <Sequence from={106}>
        <AbsoluteFill style={{transform: `translateX(${x + 1080}px)`}}><Reveal /></AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};

/* ---------- Som provisório (gerado, substituir pelo pack licenciado) ---------- */
const sfx: [number, string, number?][] = [
  [0, 'hit.wav', 0.8], [12, 'click.wav'], [24, 'click.wav'], [39, 'click.wav'], [41, 'click.wav'], [43, 'click.wav'],
  [57, 'click.wav'], [57, 'whoosh.wav', 0.8], [72, 'hit.wav', 1], [84, 'swipe.wav', 0.7],
  ...msgs.slice(0, 5).map(([t]) => [90 + t, 'notif.wav', 0.8] as [number, string, number]),
  [194, 'swipe.wav', 0.8], [200, 'whoosh.wav', 0.7], [222, 'click.wav'],
];

export const First8: React.FC<{showPlaceholders: boolean}> = ({showPlaceholders: ph}) => (
  <AbsoluteFill style={{background: '#000', fontFamily: FONT}}>
    <Sequence from={0} durationInFrames={12}><FrameA /></Sequence>
    <Sequence from={12} durationInFrames={12}><FrameB ph={ph} /></Sequence>
    <Sequence from={24} durationInFrames={15}><FrameC ph={ph} /></Sequence>
    <Sequence from={39} durationInFrames={18}><FrameD /></Sequence>
    <Sequence from={57} durationInFrames={33}><FrameEF /></Sequence>
    <Sequence from={90}><SwipeWorld /></Sequence>
    {sfx.map(([t, s, v], i) => (
      <Sequence key={i} from={t} durationInFrames={30}><Audio src={staticFile(s)} volume={v ?? 0.6} /></Sequence>
    ))}
  </AbsoluteFill>
);
