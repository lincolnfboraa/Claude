import {Composition} from 'remotion';
import {First8} from './First8';

export const Root = () => (
  <Composition
    id="BoraFirst8"
    component={First8}
    durationInFrames={240}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{showPlaceholders: true}}
  />
);
