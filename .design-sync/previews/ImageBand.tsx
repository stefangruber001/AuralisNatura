import { ImageBand } from '@auralis/design-system';
import { band } from './_assets';

export const WithCaption = () => (
  <ImageBand
    src={band}
    alt="Frisches Gemüse und ein Notizbuch auf einem Tisch"
    label="Der Ansatz"
    caption="Fundierte Wissenschaft. Persönliche Begleitung."
  />
);

export const Plain = () => (
  <ImageBand src={band} alt="Frisches Gemüse und ein Notizbuch auf einem Tisch" />
);

export const Hero = () => (
  <ImageBand
    hero
    src={band}
    alt="Frisches Gemüse und ein Notizbuch auf einem Tisch"
    caption="Verstehe deinen Körper."
  />
);
