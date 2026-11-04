import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig, Img, staticFile} from 'remotion';

export const C = {navy: '#072740', orange: '#FF5E16', beige: '#F2EADF', deep: '#0C1522'};
export const FONT = "'Inter', 'Plus Jakarta Sans', system-ui, sans-serif";

export const fill: React.CSSProperties = {position: 'absolute', inset: 0};

/** Grid de pontos navy (assinatura visual Bora) */
export const DotGrid: React.FC<{opacity?: number}> = ({opacity = 1}) => (
  <svg width={1080} height={1920} style={{...fill, opacity}}>
    <defs>
      <pattern id="dots" width={90} height={90} patternUnits="userSpaceOnUse" x={0} y={15}>
        <circle cx={45} cy={45} r={3.2} fill="#fff" fillOpacity={0.55} />
      </pattern>
      <radialGradient id="fade" cx="50%" cy="50%" r="55%">
        <stop offset="0%" stopColor="#fff" />
        <stop offset="100%" stopColor="#000" />
      </radialGradient>
      <mask id="m"><rect width={1080} height={1920} fill="url(#fade)" /></mask>
    </defs>
    <rect width={1080} height={1920} fill="url(#dots)" mask="url(#m)" />
  </svg>
);

/** Caixa de seleção laranja com handles, desenhada a partir de `start` */
export const SelectionBox: React.FC<{x: number; y: number; w: number; h: number; start: number; dur?: number}> = ({
  x, y, w, h, start, dur = 10,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const per = 2 * (w + h);
  const draw = interpolate(f, [start, start + dur], [per, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const s = 26;
  const handles = [
    [0, 0], [w / 2, 0], [w, 0], [0, h / 2], [w, h / 2], [0, h], [w / 2, h], [w, h],
  ];
  return (
    <svg width={1080} height={1920} style={fill}>
      <rect x={x} y={y} width={w} height={h} fill="none" stroke={C.orange} strokeWidth={4}
        strokeDasharray={per} strokeDashoffset={draw} />
      {handles.map(([hx, hy], i) => {
        const p = spring({frame: f - start - 4 - i * 0.6, fps, config: {damping: 14, stiffness: 260}});
        return (
          <rect key={i} x={x + hx - s / 2} y={y + hy - s / 2} width={s} height={s} fill={C.orange}
            style={{transformBox: 'fill-box', transformOrigin: 'center', transform: `scale(${p})`}} />
        );
      })}
    </svg>
  );
};

/** Celular em CSS. O conteúdo da tela é substituível pela gravação real. */
export const Phone: React.FC<{width?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({
  width = 620, children, style,
}) => {
  const h = width * 2.17;
  return (
    <div style={{width, height: h, borderRadius: width * 0.16, background: '#0d0d0f', padding: width * 0.035,
      boxShadow: '0 60px 120px rgba(0,0,0,.45), 0 0 0 3px #3a3a40 inset', position: 'relative', ...style}}>
      <div style={{width: '100%', height: '100%', borderRadius: width * 0.13, overflow: 'hidden', position: 'relative', background: C.beige}}>
        {children}
        <div style={{position: 'absolute', top: width * 0.03, left: '50%', transform: 'translateX(-50%)',
          width: width * 0.3, height: width * 0.085, borderRadius: 999, background: '#000'}} />
      </div>
    </div>
  );
};

export const Catalog: React.FC<{scroll?: number}> = ({scroll = 0}) => (
  <Img src={staticFile('ferretts_catalog.png')}
    style={{width: '100%', position: 'absolute', top: 0, transform: `translateY(${-scroll}px)`, paddingTop: 70, background: C.beige}} />
);

export const Placeholder: React.FC<{show: boolean; label: string}> = ({show, label}) =>
  show ? (
    <div style={{position: 'absolute', left: 40, bottom: 60, padding: '10px 18px', borderRadius: 8, background: 'rgba(255,94,22,.92)',
      color: '#fff', font: `600 26px ${FONT}`, letterSpacing: 1}}>PLACEHOLDER · {label}</div>
  ) : null;
