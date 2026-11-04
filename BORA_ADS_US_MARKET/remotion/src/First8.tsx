import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig, spring} from 'remotion';
import {C, CATALOG, Catalog, FONT, PhoneFrame, fill} from './brand';

/*
 V3 | 8s | 30fps | 100 BPM (tempo = 18 frames, colcheia = 9)
 0–63   montagem: T1 ouro > T2 trufa partida > T3 match cut p/ card + whip > T4 carrossel real > T5 categoria real com estoque
 63–90  problema: close nas notificações de clientes (preço / disponibilidade)
 90–150 transição única: câmera recua, revela o celular, notificações saem e o catálogo abre
 150–240 câmera gira para frontal e se aproxima, catálogo começa a rolar
*/

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const eOut = Easing.out(Easing.cubic), eIn = Easing.in(Easing.cubic), eInOut = Easing.inOut(Easing.cubic);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const kf = (f: number, frames: number[], vals: number[], e = eInOut) => interpolate(f, frames, vals, {...clamp, easing: e});

/* ---------- foto de produto ---------- */
const Photo: React.FC<{ox: number; oy: number; s: [number, number]; dx?: [number, number]; d: number; e?: (t: number) => number}> = ({ox, oy, s, dx = [0, 0], d, e = eOut}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, d], [0, 1], {...clamp, easing: e});
  const size = 1920;
  return (
    <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
      <Img src={staticFile('truffles.jpg')} style={{position: 'absolute', width: size, height: size, left: 540 - ox * size, top: 960 - oy * size,
        transformOrigin: `${ox * 100}% ${oy * 100}%`, transform: `translateX(${lerp(dx[0], dx[1], t)}px) scale(${lerp(s[0], s[1], t)})`}} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 40%, rgba(8,3,0,.6) 100%)'}} />
    </AbsoluteFill>
  );
};

/* ---------- T3: match cut trufa > card do catálogo > whip pan ---------- */
const TRUFA = {x: 600, y: 1300};
const MatchToCard = () => {
  const f = useCurrentFrame(); // 18 frames
  const t = kf(f, [0, 10], [0, 1], eOut);
  const s = lerp(3.3, 0.78, t);
  const cx = lerp(TRUFA.x, CATALOG.w / 2, t), cy = lerp(TRUFA.y, CATALOG.h / 2, t);
  const whip = kf(f, [9, 14], [0, -1500], eIn);
  const blur = Math.max(kf(f, [0, 2, 6, 10], [0, 7, 3, 0], (x) => x), kf(f, [10, 14], [0, 12], eIn));
  return (
    <AbsoluteFill style={{background: C.navy, overflow: 'hidden'}}>
      <Img src={staticFile(CATALOG.src)} style={{position: 'absolute', left: 0, top: 0, width: CATALOG.w, height: CATALOG.h, transformOrigin: '0 0',
        borderRadius: lerp(0, 40, t) / s, boxShadow: '0 60px 120px rgba(0,0,0,.5)',
        transform: `translate(${540 - cx * s + whip}px, ${960 - cy * s}px) scale(${s})`, filter: `blur(${blur}px)`}} />
    </AbsoluteFill>
  );
};

/* ---------- T4/T5: gravação real flutuando em perspectiva ---------- */
const FloatingScreen: React.FC<{src: string; d: number; ry: [number, number]; ty: [number, number]; tx?: [number, number]; s?: [number, number]; blurIn?: boolean}> = ({
  src, d, ry, ty, tx = [0, 0], s = [1, 1], blurIn,
}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [0, d], [0, 1], {...clamp, easing: eOut});
  const w = 860, h = (w * 1696) / 990;
  const blur = blurIn ? kf(f, [0, 4], [10, 0], eOut) : 0;
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 40%, #0f3d60, ${C.navy} 50%, ${C.deep})`, perspective: 2200}}>
      <div style={{position: 'absolute', left: 540 - w / 2, top: 960 - h / 2, width: w, height: h, borderRadius: 44, overflow: 'hidden', background: '#f4f5f8',
        boxShadow: '0 80px 160px rgba(0,0,0,.55), 0 0 0 2px rgba(255,255,255,.12)', filter: `blur(${blur}px)`,
        transform: `translate(${lerp(tx[0], tx[1], t)}px, ${lerp(ty[0], ty[1], t)}px) scale(${lerp(s[0], s[1], t)}) rotateY(${lerp(ry[0], ry[1], t)}deg) rotateX(6deg)`}}>
        <OffthreadVideo src={staticFile(src)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        <div style={{...fill, background: 'linear-gradient(#f4f5f8, rgba(244,245,248,0) 7%, rgba(244,245,248,0) 93%, #f4f5f8)'}} />
      </div>
    </AbsoluteFill>
  );
};

/* ---------- 2–8s: o mesmo celular do problema à solução ---------- */
const notes = [
  {t: 60, name: 'Emily R.', text: 'How much is the truffle box?', c: '#E07A5F'},
  {t: 69, name: 'Jason M.', text: 'Is this still available?', c: '#3D8BD9'},
  {t: 74, name: 'Sofia', text: 'Price for 50 pieces?', c: '#7A9E7E'},
  {t: 78, name: 'Mike T.', text: 'Do you have the strawberry one?', c: '#B58ED6'},
  {t: 82, name: 'Ana P.', text: 'Can you send me a menu?', c: '#E3A33B'},
];

const LockScreen = () => {
  const f = useCurrentFrame() + 63; // frames globais
  const {fps} = useVideoConfig();
  const clear = (i: number) => kf(f, [114 + i * 1.5, 126 + i * 1.5], [0, 1], eIn);
  return (
    <AbsoluteFill style={{background: `linear-gradient(170deg, #0f3d60, ${C.navy} 45%, ${C.deep})`, fontFamily: FONT}}>
      <div style={{position: 'absolute', top: 120, width: '100%', textAlign: 'center', color: '#fff', opacity: 1 - clear(0)}}>
        <div style={{font: `500 26px ${FONT}`, opacity: 0.8}}>Tuesday, November 4</div>
        <div style={{font: `700 130px/1.1 ${FONT}`, letterSpacing: -4}}>9:41</div>
      </div>
      <div style={{position: 'absolute', top: 400, left: 22, right: 22, display: 'flex', flexDirection: 'column', gap: 12}}>
        {notes.map((n, i) => {
          const p = spring({frame: f - n.t, fps, config: {damping: 17, stiffness: 300}});
          const c = clear(notes.length - 1 - i);
          return (
            <div key={i} style={{display: 'flex', gap: 16, alignItems: 'center', padding: '18px 20px', borderRadius: 30,
              background: 'rgba(242,234,223,.94)', boxShadow: '0 10px 30px rgba(0,0,0,.25)',
              opacity: f < n.t ? 0 : Math.min(1, p * 1.5) * (1 - c),
              transform: `translateY(${(1 - p) * -40 - c * 260}px) scale(${0.92 + 0.08 * p})`}}>
              <div style={{width: 60, height: 60, borderRadius: 30, background: n.c, color: '#fff', font: `700 26px ${FONT}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none'}}>{n.name[0]}</div>
              <div style={{flex: 1, minWidth: 0}}>
                <div style={{display: 'flex', justifyContent: 'space-between', font: `700 24px ${FONT}`, color: C.navy}}>
                  <span>{n.name}</span><span style={{fontWeight: 500, opacity: 0.55}}>now</span>
                </div>
                <div style={{font: `500 25px ${FONT}`, color: C.navy, opacity: 0.85, marginTop: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{n.text}</div>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const PhoneStory = () => {
  const f = useCurrentFrame() + 63; // trabalha em frames globais
  // câmera: close nas mensagens > recua e gira (3/4) > volta frontal e se aproxima
  const s = kf(f, [63, 90, 132, 150, 205, 240], [1.62, 1.7, 0.78, 0.8, 1.38, 1.44]);
  const ty = kf(f, [63, 90, 132, 150, 205, 240], [420, 440, 30, 30, 360, 380]);
  const ry = kf(f, [63, 90, 132, 150, 205, 240], [0, 0, -24, -22, 0, 0]);
  const rx = kf(f, [63, 90, 132, 150, 205, 240], [0, 0, 8, 8, 2, 0]);
  const sheet = kf(f, [116, 138], [1, 0], eInOut);
  const scroll = kf(f, [196, 240], [0, 110], eInOut);
  const rim = kf(f, [100, 140, 200], [0, 1, 0.4]);
  const bgBlur = kf(f, [63, 132], [24, 14]);
  const bgScale = kf(f, [63, 132, 240], [1.5, 1.15, 1.3]);
  return (
    <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
      {/* ambiente: confeitaria fora de foco */}
      <Img src={staticFile('truffles.jpg')} style={{position: 'absolute', width: 1920, height: 1920, left: -420, top: 0,
        transform: `scale(${bgScale})`, filter: `blur(${bgBlur}px) brightness(.45) saturate(1.1)`}} />
      <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(7,39,64,.55), rgba(12,21,34,.85))`}} />
      <AbsoluteFill style={{opacity: rim * 0.5, background: `radial-gradient(ellipse 40% 30% at 50% 55%, ${C.orange}, transparent 70%)`}} />
      <AbsoluteFill style={{perspective: 2400}}>
        <AbsoluteFill style={{transform: `translateY(${ty}px) scale(${s}) rotateY(${ry}deg) rotateX(${rx}deg)`, transformStyle: 'preserve-3d'}}>
          <PhoneFrame>
            <LockScreen />
            <div style={{...fill, transform: `translateY(${sheet * 100}%)`, borderRadius: 60, overflow: 'hidden', boxShadow: '0 -20px 60px rgba(0,0,0,.3)'}}>
              <Catalog scroll={scroll} />
            </div>
          </PhoneFrame>
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ---------- composição ---------- */
export const First8: React.FC = () => (
  <AbsoluteFill style={{background: '#000', fontFamily: FONT}}>
    {/* T1 ouro em detalhe, deslizando */}
    <Sequence durationInFrames={9}><Photo ox={0.47} oy={0.27} s={[2.1, 2.3]} dx={[80, -60]} d={9} e={(t) => t} /></Sequence>
    {/* T2 trufa partida, push-in acelerando até o recheio ocupar o centro */}
    <Sequence from={9} durationInFrames={9}><Photo ox={0.6} oy={0.57} s={[1.6, 2.4]} d={9} e={eIn} /></Sequence>
    {/* T3 match cut: o recheio vira o card "Trufa Tradicional", recua e chicoteia p/ esquerda */}
    <Sequence from={18} durationInFrames={18}><MatchToCard /></Sequence>
    {/* T4 continua o movimento: tela real da Papelaria entra pela direita, carrossel rolando */}
    <Sequence from={31} durationInFrames={14}><FloatingScreen src="pap_carousel.mp4" d={14} tx={[420, 0]} ry={[-14, -8]} ty={[-60, -40]} s={[1.18, 1.12]} blurIn /></Sequence>
    {/* T5 categoria abrindo com preço e estoque, câmera desce junto */}
    <Sequence from={45} durationInFrames={18}><FloatingScreen src="pap_category.mp4" d={18} ry={[10, 6]} ty={[40, -120]} s={[1.1, 1.22]} /></Sequence>
    {/* 2,1s em diante: problema > transição > reveal, tudo no mesmo celular */}
    <Sequence from={63}><PhoneStory /></Sequence>
    <Audio src={staticFile('score_v3.wav')} />
  </AbsoluteFill>
);
