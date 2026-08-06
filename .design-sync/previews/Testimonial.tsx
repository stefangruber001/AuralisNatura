/* Every quote below is a real client review taken verbatim from the production
   site. Fabricated testimonials are a hard guardrail for this brand — if you
   need a different example here, take another real one, never invent one. */
import { Testimonial, Section, Label, Heading } from '@auralis/design-system';

export const Single = () => (
  <Section tone="dark" padding="sm">
    <Testimonial
      rating={5}
      quote="Dank ihrer kompetenten und individuellen Beratung habe ich meine Ernährung nachhaltig umgestellt. Seitdem fühle ich mich wieder viel ausgeglichener und habe deutlich mehr Energie im Alltag."
      name="Rebecca E."
      role="Balance · Hausmannstätten"
    />
  </Section>
);

export const TheBand = () => (
  <Section tone="dark" padding="sm">
    <Label onDark>In ihren Worten</Label>
    <Heading level={2}>Ganz leise fühlt sich das Leben leichter an.</Heading>
    <div className="tmt-grid">
      <Testimonial
        rating={5}
        quote="Dank ihrer kompetenten und individuellen Beratung habe ich meine Ernährung nachhaltig umgestellt. Die Umstellung war alltagstauglich und leicht umzusetzen."
        name="Rebecca E."
        role="Balance · Hausmannstätten"
      />
      <Testimonial
        rating={5}
        quote="Die Ernährungsberatung ist fachlich extrem fundiert und zu 100 % auf meinen stressigen Alltag abgestimmt. Keine strikten Verbote, sondern praxisnahe Tipps."
        name="Bettina P."
        role="Klarheit · Puntigam, Österreich"
      />
      <Testimonial
        rating={5}
        quote="Die Analyse war ein echter Wendepunkt. Die Veränderungen ließen sich problemlos in meinen Alltag integrieren und haben meine Energie deutlich verbessert."
        name="Helmut P."
        role="Wandel · Graz, Österreich"
      />
    </div>
  </Section>
);

export const WithoutRating = () => (
  <Section tone="dark" padding="sm">
    <Testimonial
      quote="Die Analyse war ein echter Wendepunkt. Die Veränderungen ließen sich problemlos in meinen Alltag integrieren."
      name="Helmut P."
      role="Wandel · Graz, Österreich"
    />
  </Section>
);
