// Fonte única da timeline da abertura (30 fps, 240 frames).
// Usada pelo componente E pela rotina de verificação, para não existirem números soltos.
export const FPS = 30;
export const TOTAL = 240;
export const PROBLEM_END = 60;     // 0–59   PROBLEMA
export const SOLUTION_START = 120; // 60–119 TRANSIÇÃO | 120–239 SOLUÇÃO

export type Phase = 'PROBLEMA' | 'TRANSICAO' | 'SOLUCAO';
export const phaseAt = (f: number): Phase => (f < PROBLEM_END ? 'PROBLEMA' : f < SOLUTION_START ? 'TRANSICAO' : 'SOLUCAO');

// Dentro da transição: notificações saem, catálogo sobe e cobre a tela neste frame.
export const CATALOG_COVERS = 84;

export type Layers = {notifications: boolean; catalog: boolean; hookText: boolean; solutionText: boolean};
export const layersAt = (f: number): Layers => {
  const p = phaseAt(f);
  return {
    notifications: p === 'PROBLEMA' || (p === 'TRANSICAO' && f < CATALOG_COVERS),
    catalog: p !== 'PROBLEMA',
    hookText: p === 'PROBLEMA',
    solutionText: p === 'SOLUCAO',
  };
};
