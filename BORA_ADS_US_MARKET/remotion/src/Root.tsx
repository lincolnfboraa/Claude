import {Composition} from 'remotion';
import {Opening} from './V4';

// Abertura 8s: GANCHO (0–2s) > TRANSIÇÃO (2–2,8s) > CATÁLOGO (2,8–8s), um único celular
export const Root = () => (
  <Composition id="Opening-V5" component={Opening} durationInFrames={240} fps={30} width={1080} height={1920} />
);
