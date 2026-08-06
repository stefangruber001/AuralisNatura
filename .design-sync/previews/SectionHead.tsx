import { SectionHead, Section, Em } from '@auralis/design-system';

export const Standard = () => (
  <SectionHead
    label="Wege der Zusammenarbeit"
    title={
      <>
        Verstehen. Verändern. <Em>Dranbleiben.</Em>
      </>
    }
    sub="Jeder Weg beginnt mit einem kostenlosen Gespräch."
  />
);

export const Centered = () => (
  <SectionHead label="Gute Fragen" title="Bevor du buchst." center />
);

export const OnDark = () => (
  <Section tone="dark" padding="sm">
    <SectionHead
      onDark
      label="In ihren Worten"
      title="Ganz leise fühlt sich das Leben leichter an."
    />
  </Section>
);
