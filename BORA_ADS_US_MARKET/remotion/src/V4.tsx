import React from 'react';
import {AbsoluteFill, Audio, Easing, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, Catalog, FONT, PhoneFrame, fill} from './brand';

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
          <div style={{padding: '14px 28px', borderRadius: 999, background: C.orange, color: '#fff', font: `700 28px ${FONT}`,
            transform: `scale(${1 + 0.08 * Math.max(0, 1 - (f - EXTRA[extra - 1]) / 3)})`}}>+{extra} new messages</div>
        </div>
      )}
    </AbsoluteFill>
  );
};

export const V4Blocks23: React.FC = () => {
  const f = useCurrentFrame();
  // câmera: close nas mensagens > recua até o celular inteiro (base fora do quadro)
  const s = kf(f, [0, 45, 92, 105], [1.5, 1.56, 1.0, 1.0]);
  const ty = kf(f, [0, 45, 92, 105], [330, 350, 400, 390]);
  const sheet = kf(f, [48, 67], [1, 0], eInOut);
  const settle = kf(f, [67, 75], [1, 0], eOut); // pequeno encaixe do catálogo
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 30%, #0e3a5c, ${C.navy} 55%, ${C.deep})`, fontFamily: FONT}}>
      <AbsoluteFill style={{transform: `translateY(${ty}px) scale(${s})`}}>
        <PhoneFrame>
          <Inbox />
          <div style={{...fill, transform: `translateY(${sheet * 100 + settle * -0.8}%)`, borderRadius: 60, overflow: 'hidden'}}>
            <Catalog />
          </div>
        </PhoneFrame>
      </AbsoluteFill>
      <Audio src={staticFile('score_v4_b23.wav')} />
    </AbsoluteFill>
  );
};
