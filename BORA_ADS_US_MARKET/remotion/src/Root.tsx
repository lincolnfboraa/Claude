import {Composition} from 'remotion';
import {V4Full} from './V4';

export const Root = () => (
  <Composition id="V4-Full" component={V4Full} durationInFrames={240} fps={30} width={1080} height={1920} />
);
