import {Composition} from 'remotion';
import {V4Blocks23} from './V4';

export const Root = () => (
  <>
    {/* Preview: blocos 2 e 3 (1,5s a 5,0s do opening). Blocos 1 e 4 aguardam assets reais da Ferrett's. */}
    <Composition id="V4-Blocks2-3" component={V4Blocks23} durationInFrames={105} fps={30} width={1080} height={1920} />
  </>
);
