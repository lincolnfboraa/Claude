// Verificação pré-render: registra o estado esperado de cada frame e falha se alguma regra for violada.
import {writeFileSync, mkdirSync} from 'node:fs';
import {TOTAL, phaseAt, layersAt} from '../src/timeline.ts';
const rows = ['frame,tempo_s,fase,notificacoes,catalogo,texto_gancho,texto_solucao'];
const errors = [];
for (let f = 0; f < TOTAL; f++) {
  const p = phaseAt(f), L = layersAt(f);
  rows.push([f, (f / 30).toFixed(3), p, +L.notifications, +L.catalog, +L.hookText, +L.solutionText].join(','));
  if (f >= 120 && L.notifications) errors.push(`f${f}: notificação depois do frame 120`);
  if (L.hookText && p !== 'PROBLEMA') errors.push(`f${f}: texto do gancho fora do PROBLEMA`);
  if (L.solutionText && p !== 'SOLUCAO') errors.push(`f${f}: texto da solução fora da SOLUÇÃO`);
  if (p === 'PROBLEMA' && L.catalog) errors.push(`f${f}: catálogo durante o PROBLEMA`);
  if (p === 'SOLUCAO' && !L.catalog) errors.push(`f${f}: SOLUÇÃO sem catálogo`);
}
// a sequência de fases precisa ser monotônica (sem voltar)
const order = ['PROBLEMA', 'TRANSICAO', 'SOLUCAO'];
for (let f = 1; f < TOTAL; f++) if (order.indexOf(phaseAt(f)) < order.indexOf(phaseAt(f - 1))) errors.push(`f${f}: fase voltou`);
mkdirSync(new URL('../out/', import.meta.url), {recursive: true});
writeFileSync(new URL('../out/timeline_log.csv', import.meta.url), rows.join('\n'));
const runs = []; let s = 0;
for (let f = 1; f <= TOTAL; f++) if (f === TOTAL || phaseAt(f) !== phaseAt(s)) { runs.push(`${phaseAt(s)} ${s}-${f - 1}`); s = f; }
console.log('fases:', runs.join(' | '));
if (errors.length) { console.error('FALHOU:\n' + errors.join('\n')); process.exit(1); }
console.log('timeline OK (240 frames, log em out/timeline_log.csv)');
