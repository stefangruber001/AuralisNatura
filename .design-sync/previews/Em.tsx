import { Em, Display, Heading, Section } from '@auralis/design-system';

export const TheTurnInAHeadline = () => (
  <Display>
    Verstehe deinen Körper. <Em>Verbessere deine Gesundheit nachhaltig.</Em>
  </Display>
);

export const InASectionHeading = () => (
  <Heading level={2}>
    Den Körper verstehen. <Em>Den Menschen sehen.</Em>
  </Heading>
);

export const OnADarkBand = () => (
  <Section tone="dark" padding="sm">
    <Heading level={2}>
      Dein Körper sendet Signale. <Em>Finden wir heraus, was dahintersteckt.</Em>
    </Heading>
  </Section>
);
