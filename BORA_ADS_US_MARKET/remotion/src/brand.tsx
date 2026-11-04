import React from 'react';
import {Img, staticFile} from 'remotion';

export const C = {navy: '#072740', orange: '#FF5E16', beige: '#F2EADF', deep: '#0C1522'};
export const FONT = "'Inter', 'Plus Jakarta Sans', system-ui, sans-serif";
export const fill: React.CSSProperties = {position: 'absolute', inset: 0};

/** Grid de pontos discreto (textura de fundo Bora) */
export const DotGrid: React.FC<{opacity?: number}> = ({opacity = 1}) => (
  <svg width={1080} height={1920} style={{...fill, opacity}}>
    <defs>
      <pattern id="dots" width={90} height={90} patternUnits="userSpaceOnUse" x={0} y={15}>
        <circle cx={45} cy={45} r={2.6} fill="#fff" fillOpacity={0.5} />
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

/** Geometria do celular, compartilhada pela transição mensagens > tela */
export const PHONE = {w: 680, cx: 540, cy: 960};
export const phoneH = PHONE.w * 2.17;
export const bezel = PHONE.w * 0.035;
export const SCREEN = {
  x: PHONE.cx - PHONE.w / 2 + bezel,
  y: PHONE.cy - phoneH / 2 + bezel,
  w: PHONE.w - 2 * bezel,
  h: phoneH - 2 * bezel,
  r: PHONE.w * 0.13,
};

export const PhoneFrame: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div style={{position: 'absolute', left: PHONE.cx - PHONE.w / 2, top: PHONE.cy - phoneH / 2, width: PHONE.w, height: phoneH,
    borderRadius: PHONE.w * 0.16, background: '#0d0d0f', padding: bezel,
    boxShadow: '0 70px 140px rgba(0,0,0,.5), 0 0 0 3px #3a3a40 inset', ...style}}>
    <div style={{width: '100%', height: '100%', borderRadius: SCREEN.r, overflow: 'hidden', position: 'relative', background: C.beige}}>
      {children}
      <div style={{position: 'absolute', top: PHONE.w * 0.03, left: '50%', transform: 'translateX(-50%)',
        width: PHONE.w * 0.3, height: PHONE.w * 0.085, borderRadius: 999, background: '#000'}} />
    </div>
  </div>
);

/** Interface real do Ferrett's (print 1320x2420, sem barras do navegador) */
export const CATALOG = {src: 'ferretts_catalog.png', w: 1320, h: 2420};
export const Catalog: React.FC<{scroll?: number}> = ({scroll = 0}) => (
  <Img src={staticFile(CATALOG.src)}
    style={{width: '100%', position: 'absolute', top: 0, transform: `translateY(${-scroll}px)`, paddingTop: 64, background: C.beige}} />
);
