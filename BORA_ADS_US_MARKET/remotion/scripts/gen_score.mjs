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

// 0–1,5s montagem: kick nos tempos, hat nas colcheias (= cortes), baixo pulsando
for (const f of [0, 12, 24, 36]) kick(F(f));
for (let f = 0; f < 39; f += 6) hatEnv(F(f), 0.22);
for (const f of [0, 12, 24]) tone(F(f), 0.38, 55, 0.35, 0.01, 5);
noise(F(36), F(9), (k) => k * k, 0.5); sweep(F(36), F(9), 300, 1400, 0.12); // riser para o logo
// 1,5s logo: impacto + boom + brilho curto (protótipo de logo sonoro)
kick(F(45), 1.3); tone(F(45), 1.4, 41, 0.5, 0.01, 2.4); noise(F(45), 0.5, (k) => Math.exp(-k * 6), 0.35);
tone(F(47), 0.9, 1318.5, 0.07, 0.003, 4); tone(F(49), 0.9, 1975.5, 0.05, 0.003, 4);
noise(F(70), F(7), (k) => Math.sin(Math.PI * k), 0.25); // whoosh de saída
// 2,5–4,5s gancho: batida volta, notificações nas mensagens, tensão crescente
for (let f = 75; f < 135; f += 12) kick(F(f), 0.8);
for (let f = 81; f < 135; f += 12) hatEnv(F(f), 0.15);
[80, 89, 97, 104, 110, 115].forEach((f, i) => { tone(F(f), 0.08, 1046 + i * 40, 0.12, 0.002, 30); tone(F(f) + 0.07, 0.12, 1568 + i * 40, 0.1, 0.002, 25); });
tone(F(75), 2, 58.3, 0.18, 0.2, 0.5);
// 4,5–6s transição: as mensagens se fundem, riser sobe
noise(F(136), F(44), (k) => k * k * k, 0.55); sweep(F(140), F(40), 200, 900, 0.1);
tone(F(161), 0.05, 2400, 0.12, 0.001, 60); // tick de UI quando a tela acende
// 6s reveal: impacto suave + acorde maior abrindo
kick(F(180), 1.0); noise(F(180), 0.4, (k) => Math.exp(-k * 7), 0.25);
for (const [f, g] of [[110, 0.12], [220, 0.1], [277.18, 0.08], [329.63, 0.08], [440, 0.05], [554.37, 0.04]])
  add(F(180), 2, (x) => (2 / Math.PI) * Math.asin(Math.sin(2 * Math.PI * f * x)) * Math.min(1, x / 0.25) * Math.exp(-x * 0.6), g);
for (const f of [192, 204, 216, 228]) hatEnv(F(f), 0.1);
for (const f of [204, 228]) kick(F(f), 0.6);

let peak = 0; for (const v of L) peak = Math.max(peak, Math.abs(v));
const g = 0.89 / peak, buf = Buffer.alloc(44 + N * 2);
buf.write('RIFF', 0); buf.writeUInt32LE(36 + N * 2, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16);
buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 2, 28);
buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(N * 2, 40);
for (let i = 0; i < N; i++) buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * g)) * 32767), 44 + i * 2);
writeFileSync(new URL('../public/score_v2.wav', import.meta.url), buf);
console.log('score_v2.wav ok');
