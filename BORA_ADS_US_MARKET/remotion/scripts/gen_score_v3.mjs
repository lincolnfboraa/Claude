// Trilha provisória sintetizada (150 BPM, colcheia = 6 frames a 30fps).
// Serve só para marcar ritmo e sincronia. Substituir por trilha + SFX licenciados.
import {writeFileSync} from 'node:fs';
const SR = 44100, DUR = 8, N = SR * DUR, L = new Float32Array(N);
const F = (f) => f / 30;
let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;
const add = (t0, dur, fn, gain = 1) => {
  const s0 = Math.floor(t0 * SR);
  for (let i = 0; i < dur * SR && s0 + i < N; i++) L[s0 + i] += fn(i / SR) * gain;
};
const kick = (t, g = 1) => { let ph = 0; add(t, 0.4, (x) => { ph += (2 * Math.PI * (45 + 110 * Math.exp(-x * 28))) / SR; return Math.sin(ph) * Math.exp(-x * 8); }, g); };
const hat = (t, g = 0.18) => { let p = 0; add(t, 0.06, () => { const n = rnd(); const h = n - p; p = n; return h * 0.5; }, g); add(t, 0.06, (x) => 0, 0); };
const hatEnv = (t, g = 0.18) => { let p = 0; add(t, 0.07, (x) => { const n = rnd(); const h = n - p; p = n; return h * Math.exp(-x * 70); }, g); };
const tone = (t, dur, f, g, a = 0.005, d = 6) => add(t, dur, (x) => Math.sin(2 * Math.PI * f * x) * Math.min(1, x / a) * Math.exp(-x * d), g);
const noise = (t, dur, env, g) => { let lp = 0; add(t, dur, (x) => { lp += (rnd() - lp) * 0.25; return lp * env(x / dur); }, g); };
const sweep = (t, dur, f0, f1, g) => { let ph = 0; add(t, dur, (x) => { const k = x / dur; ph += (2 * Math.PI * (f0 + (f1 - f0) * k * k)) / SR; return Math.sin(ph) * k * k; }, g); };

// V3: 100 BPM, tempo = 18 frames, colcheia = 9 frames (cortes em 0, 9, 18, 36, 45, 63)
for (const f of [0, 18, 36, 54]) kick(F(f));
for (let f = 0; f < 63; f += 9) hatEnv(F(f), 0.22);
for (const f of [0, 18, 36]) tone(F(f), 0.55, 49, 0.35, 0.01, 4);
noise(F(26), F(10), (k) => Math.sin(Math.PI * k), 0.45);            // whip pan do T3
noise(F(31), 0.12, (k) => Math.exp(-k * 5), 0.25);                   // entrada do T4
tone(F(45), 0.05, 2200, 0.1, 0.001, 60);                             // tick no corte do T5
// problema: batida some, pings acelerando, drone de tensão
[63, 69, 74, 78, 82].forEach((f, i) => { tone(F(f), 0.08, 1046 + i * 60, 0.13, 0.002, 30); tone(F(f) + 0.07, 0.12, 1568 + i * 60, 0.1, 0.002, 25); });
tone(F(63), 2.2, 58.3, 0.22, 0.15, 0.6);
// transição contínua: riser na recuada, swipe quando as notificações saem, abre o app
noise(F(90), F(42), (k) => k * k, 0.4); sweep(F(92), F(40), 180, 760, 0.1);
noise(F(114), F(12), (k) => Math.sin(Math.PI * k), 0.45);
tone(F(138), 0.05, 2400, 0.12, 0.001, 60);
// reveal: impacto quando a câmera começa a avançar + acorde + batida volta
kick(F(153), 1.3); tone(F(153), 1.2, 41, 0.45, 0.01, 2.6); noise(F(153), 0.4, (k) => Math.exp(-k * 7), 0.25);
for (const [fr, g] of [[110, 0.12], [220, 0.1], [277.18, 0.08], [329.63, 0.08], [440, 0.05], [554.37, 0.04]])
  add(F(153), 2.9, (x) => (2 / Math.PI) * Math.asin(Math.sin(2 * Math.PI * fr * x)) * Math.min(1, x / 0.3) * Math.exp(-x * 0.5), g);
for (const f of [171, 189, 207, 225]) kick(F(f), 0.7);
for (let f = 162; f < 240; f += 9) hatEnv(F(f), 0.12);
noise(F(196), F(14), (k) => Math.sin(Math.PI * k), 0.18);            // início da rolagem

let peak = 0; for (const v of L) peak = Math.max(peak, Math.abs(v));
const g = 0.89 / peak, buf = Buffer.alloc(44 + N * 2);
buf.write('RIFF', 0); buf.writeUInt32LE(36 + N * 2, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16);
buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 2, 28);
buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(N * 2, 40);
for (let i = 0; i < N; i++) buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * g)) * 32767), 44 + i * 2);
writeFileSync(new URL('../public/score_v3.wav', import.meta.url), buf);
console.log('score_v3.wav ok');
