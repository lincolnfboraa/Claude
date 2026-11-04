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
  {t: 12, name: 'Jason M.', text: 'Do you have strawberry?', c: '#3D7FC1'},
  {t: 20, name: 'Sofia L.', text: 'Can you send me the menu?', c: '#6E9773'},
  {t: 26, name: 'Mike T.', text: 'Price for 50 pieces?', c: '#9B7BC0'},
];
const EXTRA = [30, 33, 35.5, 38, 40, 42, 44, 46]; // rajada final, vira o contador

const CARD_H = 132, GAP = 14;
// timeline: 0–45 notificações | 45–67 transição (sheet 48–67) | 67–105 só catálogo + câmera
// timeline V5: 0–60 gancho | 60–84 transição | 84+ só catálogo
const TRANSITION_START = 60, CATALOG_COVERS = 84;

const Inbox: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const extra = EXTRA.filter((t) => f >= t).length;
  const out = (i: number) => kf(f, [60 + i * 2, 75 + i * 2], [0, 1], eIn); // mais nova sai primeiro
  const arrived = msgs.filter((m) => f >= m.t);
  return (
    <AbsoluteFill style={{background: `linear-gradient(170deg, #0f3d60, ${C.navy} 50%, ${C.deep})`}}>
      <div style={{position: 'absolute', top: 110, width: '100%', textAlign: 'center', color: '#fff', opacity: kf(f, [58, 64], [1, 0])}}>
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
const SCROLL_START = 120, SWITCH = 140, REC_FRAMES = 38; // frames locais da cena do celular

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
  // enquadramento fixo: texto no topo, celular inteiro embaixo; só pequenas variações de escala
  const s = kf(f, [0, 60, CATALOG_COVERS, 120, 240], [1.0, 1.03, 0.99, 1.02, 1.06]) + punch;
  const ty = 250;
  const sheet = kf(f, [63, CATALOG_COVERS], [1, 0], eInOut);
  const hookIn = kf(f, [-5, 5], [0, 1], eOut), hookOut = kf(f, [58, 68], [0, 1], eIn);
  const line = kf(f, [128, 140], [0, 1], eOut);
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
      {/* GANCHO: some antes da transição */}
      {f < 68 && (
        <div style={{position: 'absolute', top: 120, left: 60, right: 60, textAlign: 'center', color: '#fff',
          font: `800 76px/1.08 ${FONT}`, letterSpacing: -2.2, opacity: hookIn * (1 - hookOut), transform: `translateY(${(1 - hookIn) * 30 - hookOut * 40}px)`}}>
          Still answering<br />the <span style={{color: C.orange}}>same questions</span><br />all day?
        </div>
      )}
      {/* SOLUÇÃO: entra com o catálogo já na tela e permanece até o fim */}
      {f >= 128 && (
        <div style={{position: 'absolute', top: 170, left: 60, right: 60, textAlign: 'center', color: '#fff',
          font: `800 76px/1.08 ${FONT}`, letterSpacing: -2.2, opacity: line, transform: `translateY(${(1 - line) * 30}px)`}}>
          Let your customers<br /><span style={{color: C.orange}}>browse and order.</span>
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ---------- abertura V5: uma única cena no mesmo celular ---------- */
export const Opening: React.FC = () => (
  <AbsoluteFill style={{background: '#000'}}>
    <PhoneScene />
    <Audio src={staticFile('score_v5.wav')} />
  </AbsoluteFill>
);
