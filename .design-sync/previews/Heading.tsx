import { Heading, Em } from '@auralis/design-system';

export const SectionHeading = () => (
  <Heading level={2}>
    Dein Körper sendet Signale.
    <br />
    <Em>Finden wir heraus, was dahintersteckt.</Em>
  </Heading>
);

export const CardHeading = () => <Heading level={3}>Klarheit</Heading>;

export const Levels = () => (
  <div style={{ display: 'grid', gap: 18 }}>
    <Heading level={2}>Verstehen. Verändern. Dranbleiben.</Heading>
    <Heading level={3}>Enthalten sind:</Heading>
  </div>
);
