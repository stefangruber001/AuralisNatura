import { CtaCard, Button } from '@auralis/design-system';

export const Closing = () => (
  <CtaCard
    label="Kostenlos & unverbindlich"
    title={
      <>
        Buche dein kostenloses
        <br /> Erstgespräch.
      </>
    }
    body="In einem ruhigen Gespräch ohne Verpflichtung schauen wir gemeinsam, wo du gerade stehst und was dir wirklich helfen würde."
  />
);

export const WithAside = () => (
  <CtaCard
    label="Kostenlos & unverbindlich"
    title={
      <>
        Buche dein kostenloses
        <br /> Erstgespräch.
      </>
    }
    body="25 Minuten, in denen wir schauen, wo du stehst — und ob wir zusammenpassen."
    aside={
      <Button variant="clay" size="lg" arrow subLabel="kostenlos und unverbindlich">
        Termin auswählen
      </Button>
    }
  />
);
