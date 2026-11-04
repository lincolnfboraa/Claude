import {Config} from '@remotion/cli/config';
Config.setVideoImageFormat('jpeg');
// Container local: usa o Chromium pré-instalado. Na máquina de vocês pode remover esta linha.
if (process.env.REMOTION_CHROME) Config.setBrowserExecutable(process.env.REMOTION_CHROME);
