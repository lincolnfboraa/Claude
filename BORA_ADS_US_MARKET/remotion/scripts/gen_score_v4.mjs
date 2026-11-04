// Trilha provisória sintetizada (150 BPM, colcheia = 6 frames a 30fps).
// Serve só para marcar ritmo e sincronia. Substituir por trilha + SFX licenciados.
import {writeFileSync} from 'node:fs';
const SR = 44100, DUR = 3.5, N = SR * DUR, L = new Float32Array(N);
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

// V4 preview: blocos 2 e 3 (frame 0 = 1,5s do filme)
// Bloco 2: pings acelerando + 8 mensagens extras chegando em rajada, drone de tensão
[0, 15, 24, 30].forEach((f, i) => { tone(F(f), 0.08, 1046 + i * 50, 0.14, 0.002, 30); tone(F(f) + 0.07, 0.12, 1568 + i * 50, 0.11, 0.002, 25); });
[34, 36.5, 38.5, 40, 41.5, 42.5, 43.5, 44.3].forEach((f, i, a) => {
  tone(F(f), 0.06, 1568 + i * 30, 0.06 + i * 0.008, 0.002, 40);   // ping
  tone(F(f), 0.16, 150, 0.22 + i * 0.02, 0.002, 22);               // thump do selo laranja
  if (i === a.length - 1) { kick(F(f), 0.7); tone(F(f), 0.12, 2093, 0.08, 0.002, 30); } // ápice
});
tone(0, 1.5, 58.3, 0.2, 0.3, 0.4); tone(0, 1.5, 87.3, 0.07, 0.4, 0.5);
// Bloco 3: whoosh na subida, tick quando o catálogo encaixa, acorde de alívio
noise(F(45), F(22), (k) => Math.sin(Math.PI * k) * (0.4 + 0.6 * k), 0.45);
tone(F(67), 0.05, 2400, 0.14, 0.001, 60);
kick(F(67), 1.4); tone(F(67), 1.3, 41, 0.5, 0.01, 2.4); noise(F(67), 0.35, (k) => Math.exp(-k * 6), 0.3); // impacto do reveal
for (const [fr, g] of [[110, 0.1], [220, 0.08], [277.18, 0.06], [329.63, 0.06], [440, 0.04]])
  add(F(67), 1.3, (x) => (2 / Math.PI) * Math.asin(Math.sin(2 * Math.PI * fr * x)) * Math.min(1, x / 0.25) * Math.exp(-x * 0.9), g);

let peak = 0; for (const v of L) peak = Math.max(peak, Math.abs(v));
const g = 0.89 / peak, buf = Buffer.alloc(44 + N * 2);
buf.write('RIFF', 0); buf.writeUInt32LE(36 + N * 2, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16);
buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 2, 28);
buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(N * 2, 40);
for (let i = 0; i < N; i++) buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * g)) * 32767), 44 + i * 2);
writeFileSync(new URL('../public/score_v4_b23.wav', import.meta.url), buf);
console.log('score_v4_b23.wav ok');
