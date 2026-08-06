import { Label, Heading, Em, Section } from '@auralis/design-system';

export const Kicker = () => (
  <div>
    <Label kicker>Die Gründerin</Label>
    <Heading level={2}>
      Den Körper verstehen. <Em>Den Menschen sehen.</Em>
    </Heading>
  </div>
);

export const Plain = () => <Label>Kostenlos & unverbindlich</Label>;

export const OnDark = () => (
  <Section tone="dark" padding="sm">
    <Label onDark>Wege der Zusammenarbeit</Label>
    <Heading level={2}>Verstehen. Verändern. Dranbleiben.</Heading>
  </Section>
);
