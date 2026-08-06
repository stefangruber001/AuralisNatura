import { Section, Label, Heading, Text, Em, Button } from '@auralis/design-system';

export const Paper = () => (
  <Section>
    <Label kicker>Der Ansatz</Label>
    <Heading level={2}>
      Verstehen kommt zuerst. <Em>Dann verändern.</Em>
    </Heading>
    <Text variant="lead">
      Wir schauen gemeinsam auf deinen Alltag, bevor wir irgendetwas ändern.
    </Text>
  </Section>
);

export const Dark = () => (
  <Section tone="dark">
    <Label onDark>Warum Auralis</Label>
    <Heading level={2}>
      Dein Körper sendet Signale. <Em>Finden wir heraus, was dahintersteckt.</Em>
    </Heading>
    <Text variant="lead">
      Du brauchst keine weiteren Regeln und keine strengere Disziplin.{' '}
      <strong>Es geht nicht um die nächste Diät.</strong>
    </Text>
  </Section>
);

export const Cream = () => (
  <Section tone="cream">
    <Label kicker>Kostenlos & unverbindlich</Label>
    <Heading level={2}>Lernen wir uns kennen.</Heading>
    <Button variant="clay" arrow>
      Kostenloses Gespräch buchen
    </Button>
  </Section>
);

export const TightPadding = () => (
  <Section tone="cream" padding="sm">
    <Label kicker>Zwischenspiel</Label>
    <Text variant="lead">
      Eine kurze Zwischensektion mit engerem vertikalen Rhythmus.
    </Text>
  </Section>
);
