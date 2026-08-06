import { Text, Section, Heading, Label } from '@auralis/design-system';

export const Variants = () => (
  <div style={{ maxWidth: 620, display: 'grid', gap: 14 }}>
    <Text variant="lead">Jeder Weg beginnt mit einem kostenlosen Gespräch.</Text>
    <Text variant="big">
      Auralis Natura ist aus einer einfachen Überzeugung entstanden: Gute Gesundheit
      braucht solide Wissenschaft — und sie braucht Zeit, Zuhören und Vertrauen.
    </Text>
    <Text>
      Ich bin Desiree Gruber, promovierte Chemikerin. Mehr als fünfzehn Jahre in der
      Forschung haben geprägt, wie ich arbeite: präzise, strukturiert, evidenzbasiert.
    </Text>
  </div>
);

export const WithEmphasis = () => (
  <div style={{ maxWidth: 620 }}>
    <Text>
      <strong>Es geht nicht um die nächste Diät.</strong> Es geht darum, deine Ernährung so
      zu gestalten, dass sie zu deinem Leben passt — und dort auch bleibt.
    </Text>
  </div>
);

export const OnADarkBand = () => (
  <Section tone="dark" padding="sm">
    <Label onDark>Warum Auralis</Label>
    <Heading level={2}>Du brauchst nicht mehr Druck.</Heading>
    <Text variant="lead">
      Du brauchst keine weiteren Regeln und keine strengere Disziplin.{' '}
      <strong>Es geht nicht um die nächste Diät.</strong>
    </Text>
  </Section>
);
