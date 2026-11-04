import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, CATALOG, FONT, PhoneFrame, SCREEN, StatusBar, fill} from './brand';

/*
 V4 | preview dos blocos 2 e 3 (frame 0 = 1,5s do filme, 105 frames = 3,5s)
 Bloco 2 (0–45)  dor: perguntas chegando cada vez mais rápido, sempre legíveis
 Bloco 3 (45–105) virada: mensagens sobem, catálogo Ferrett's sobe no lugar, câmera recua
*/

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const eOut = Easing.out(Easing.cubic), eIn = Easing.in(Easing.cubic), eInOut = Easing.inOut(Easing.cubic);
const kf = (f: number, i: number[], o: number[], e = eInOut) => interpolate(f, i, o, {...clamp, easing: e});

const msgs = [
  {t: -4, name: 'Emily R.', text: 'How much is the truffle box?', c: '#C8664B'},
  {t: 15, name: 'Jason M.', text: 'Do you have strawberry?', c: '#3D7FC1'},
  {t: 24, name: 'Sofia L.', text: 'Can you send me the menu?', c: '#6E9773'},
  {t: 30, name: 'Mike T.', text: 'Price for 50 pieces?', c: '#9B7BC0'},
];
const EXTRA = [34, 36.5, 38.5, 40, 41.5, 42.5, 43.5, 44.3]; // rajada final, vira o contador

const CARD_H = 132, GAP = 14;
// timeline: 0–45 notificações | 45–67 transição (sheet 48–67) | 67–105 só catálogo + câmera
const TRANSITION_START = 45, CATALOG_COVERS = 67;

const Inbox: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const extra = EXTRA.filter((t) => f >= t).length;
  const out = (i: number) => kf(f, [45 + i * 2, 60 + i * 2], [0, 1], eIn); // mais nova sai primeiro
  const arrived = msgs.filter((m) => f >= m.t);
  return (
    <AbsoluteFill style={{background: `linear-gradient(170deg, #0f3d60, ${C.navy} 50%, ${C.deep})`}}>
      <div style={{position: 'absolute', top: 110, width: '100%', textAlign: 'center', color: '#fff', opacity: kf(f, [43, 49], [1, 0])}}>
        <div style={{font: `700 120px/1 ${FONT}`, letterSpacing: -4}}>9:41</div>
      </div>
      {/* pilha: a mais nova entra no topo e empurra as outras */}
      {arrived.map((m, idx) => {
        const order = arrived.length - 1 - idx; // 0 = topo
        const pop = spring({frame: f - m.t - 2, fps, config: {damping: 18, stiffness: 320}});
        const slot = spring({frame: f - (arrived[arrived.length - 1].t) + 1, fps, config: {damping: 24, stiffness: 600}});
        const prevOrder = Math.max(0, order - 1);
        const y = 330 + (order === 0 ? 0 : (prevOrder + (order - prevOrder) * slot) * (CARD_H + GAP));
        const o = out(order);
        return (
          <div key={m.name} style={{position: 'absolute', left: 22, right: 22, top: y, height: CARD_H, borderRadius: 34,
            background: 'rgba(242,234,223,.97)', boxShadow: '0 14px 34px rgba(0,0,0,.28)', display: 'flex', alignItems: 'center', gap: 18, padding: '0 24px',
            opacity: Math.min(1, pop * 1.4) * (1 - o), transform: `translateY(${(1 - pop) * -50 - o * 700}px) scale(${0.94 + 0.06 * pop})`}}>
            <div style={{width: 66, height: 66, borderRadius: 33, background: m.c, color: '#fff', font: `700 28px ${FONT}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none'}}>{m.name[0]}</div>
            <div style={{flex: 1}}>
              <div style={{display: 'flex', justifyContent: 'space-between', font: `700 26px ${FONT}`, color: C.navy}}>
                <span>{m.name}</span><span style={{fontWeight: 500, opacity: 0.5}}>now</span>
              </div>
              <div style={{font: `500 30px ${FONT}`, color: C.navy, marginTop: 4}}>{m.text}</div>
            </div>
          </div>
        );
      })}
      {/* contador das mensagens que não cabem mais */}
      {extra > 0 && (
        <div style={{position: 'absolute', left: 0, right: 0, top: 330 + 4 * (CARD_H + GAP) + 10, display: 'flex', justifyContent: 'center',
          opacity: 1 - out(4), transform: `translateY(${-out(4) * 700}px)`}}>
          {/* cada mensagem nova: pop do selo + anel laranja expandindo (sincronizado com o thump) */}
          <div style={{position: 'relative'}}>
            <div style={{position: 'absolute', inset: 0, borderRadius: 999, border: `4px solid ${C.orange}`,
              opacity: 0.8 * Math.max(0, 1 - (f - EXTRA[extra - 1]) / 6),
              transform: `scale(${1 + 0.45 * Math.min(1, (f - EXTRA[extra - 1]) / 6)})`}} />
            <div style={{padding: '16px 32px', borderRadius: 999, background: C.orange, color: '#fff', font: `800 32px ${FONT}`,
              boxShadow: '0 10px 30px rgba(255,94,22,.45)',
              transform: `scale(${1 + (extra === EXTRA.length ? 0.32 : 0.2) * Math.max(0, 1 - (f - EXTRA[extra - 1]) / 4)})`}}>+{extra} new messages</div>
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ---------- página do catálogo: print (topo) + gravação real alinhada pixel a pixel ---------- */
// linha 0 do recorte da gravação = linha 1582 do print (alinhamento medido por template matching)
const REC_AT = 1582, PAGE_BG = '#F8EFE4', TOP = 74;
const SCROLL_START = 105, SWITCH = 123, REC_FRAMES = 38; // frames locais da cena do celular

const Page: React.FC<{f: number}> = ({f}) => {
  const k = SCREEN.w / CATALOG.w;
  const X = kf(f, [SCROLL_START, SWITCH], [0, REC_AT], eInOut); // scroll em px do print
  const img = (src: string, top: number) => (
    <Img src={staticFile(src)} style={{position: 'absolute', left: 0, width: '100%', top}} />
  );
  return (
    <div style={{...fill, background: PAGE_BG, overflow: 'hidden'}}>
      {f < SWITCH ? (
        <>
          {img('ferretts_rec_still.png', TOP + (REC_AT - X) * k)}
          {img(CATALOG.src, TOP - X * k)}
        </>
      ) : f < SWITCH + REC_FRAMES ? (
        <Sequence from={SWITCH} layout="none">
          <OffthreadVideo src={staticFile('ferretts_rec_2x.mp4')} muted style={{position: 'absolute', left: 0, width: '100%', top: TOP}} />
        </Sequence>
      ) : (
        img('ferretts_rec_end.png', TOP)
      )}
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: TOP, background: PAGE_BG}} />
      <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: 170, background: `linear-gradient(rgba(248,239,228,0), ${PAGE_BG} 75%)`}} />
    </div>
  );
};

/* ---------- cena do celular: blocos 2, 3 e 4 num único plano (frame 0 = 1,5s do filme) ---------- */
export const PhoneScene: React.FC = () => {
  const f = useCurrentFrame();
  const punch = f >= CATALOG_COVERS ? 0.035 * Math.exp(-(f - CATALOG_COVERS) / 4) : 0;
  const s = kf(f, [0, 45, CATALOG_COVERS, 105, 161, 177], [1.2, 1.23, 1.12, 1.17, 1.19, 1.1]) + punch;
  const ty = kf(f, [161, 177], [0, 300]);
  const sheet = kf(f, [48, CATALOG_COVERS], [1, 0], eInOut);
  const line = kf(f, [169, 181], [0, 1], eOut);
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 30%, #0e3a5c, ${C.navy} 55%, ${C.deep})`, fontFamily: FONT}}>
      <AbsoluteFill style={{transform: `translateY(${ty}px) scale(${s})`}}>
        <PhoneFrame>
          {f < CATALOG_COVERS && <Inbox />}
          {f >= TRANSITION_START && (
            <div style={{...fill, transform: `translateY(${sheet * 100}%)`, borderRadius: 60, overflow: 'hidden'}}>
              <Page f={f} />
            </div>
          )}
          <StatusBar color={sheet > 0.06 ? '#fff' : C.navy} />
        </PhoneFrame>
      </AbsoluteFill>
      {/* frase final: só depois que o scroll para */}
      {f >= 169 && (
        <div style={{position: 'absolute', top: 170, left: 60, right: 60, textAlign: 'center', color: '#fff',
          font: `800 76px/1.08 ${FONT}`, letterSpacing: -2.2, opacity: line, transform: `translateY(${(1 - line) * 30}px)`}}>
          Let customers <span style={{color: C.orange}}>browse</span><br />before they ask.
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ---------- bloco 1: produto (0–1,5s, 5 takes de 9 frames no grid de 100 BPM) ---------- */
const Shot: React.FC<{src: string; ox: number; oy: number; s: [number, number]; dx?: [number, number]; r?: [number, number]; e?: (t: number) => number}> = ({
  src, ox, oy, s: sc, dx = [0, 0], r = [0, 0], e = eOut,
}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, 9], [0, 1], {...clamp, easing: e});
  const L = (a: [number, number]) => a[0] + (a[1] - a[0]) * t;
  return (
    <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
      <Img src={staticFile(src)} style={{position: 'absolute', width: 1920, height: 1920, left: 540 - ox * 1920, top: 960 - oy * 1920,
        transformOrigin: `${ox * 100}% ${oy * 100}%`, transform: `translateX(${L(dx)}px) scale(${L(sc)}) rotate(${L(r)}deg)`}} />
    </AbsoluteFill>
  );
};

export const V4Full: React.FC = () => (
  <AbsoluteFill style={{background: '#000'}}>
    <Sequence durationInFrames={9}><Shot src="b1_strawberry_dip.jpg" ox={0.45} oy={0.45} s={[1.15, 1.3]} /></Sequence>
    <Sequence from={9} durationInFrames={9}><Shot src="b1_strawberry_drizzle.jpg" ox={0.5} oy={0.52} s={[1.2, 1.2]} dx={[70, -70]} e={(t) => t} /></Sequence>
    <Sequence from={18} durationInFrames={9}><Shot src="b1_truffle_cut.jpg" ox={0.47} oy={0.52} s={[1.15, 1.35]} /></Sequence>
    <Sequence from={27} durationInFrames={9}><Shot src="b1_brigadeiro_tray.jpg" ox={0.5} oy={0.55} s={[1.15, 1.2]} dx={[-50, 50]} e={(t) => t} /></Sequence>
    <Sequence from={36} durationInFrames={9}><Shot src="b1_bonbon_box.jpg" ox={0.53} oy={0.5} s={[1.35, 1.08]} r={[6, 0]} /></Sequence>
    <Sequence from={45}><PhoneScene /></Sequence>
    <Audio src={staticFile('score_v4_full.wav')} />
  </AbsoluteFill>
);
