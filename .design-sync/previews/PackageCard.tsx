import { PackageCard, PackageGrid } from '@auralis/design-system';

export const Standard = () => (
  <PackageCard
    tag="Standortbestimmung & Gesundheitsanalyse"
    name="Klarheit"
    priceLabel="Individuelle Beratung"
    price="€199"
    description={
      <>
        <strong>Klarheit zeigt dir, wo deine Gesundheit heute steht.</strong> Gemeinsam
        erfassen wir deine Gewohnheiten, deine Umstände und deine Ziele.
      </>
    }
    featuresLabel="Enthalten sind:"
    features={[
      { text: 'Ausführlicher Gesundheitsfragebogen' },
      { text: 'Persönlicher schriftlicher Bericht' },
      { text: '60-minütiges 1:1-Gespräch' },
      { text: 'Konkrete erste Schritte' },
    ]}
    ctaLabel="Programm Klarheit buchen"
    ctaHref="#klarheit"
  />
);

export const Featured = () => (
  <PackageCard
    featured
    tag="Gesundheit im Alltag verankern · 12 Wochen"
    name="Balance"
    priceLabel="Intensive Begleitung"
    price="€899"
    description={
      <>
        <strong>Zwölf Wochen intensive Begleitung.</strong> Verstehen, umsetzen und
        dauerhaft halten — mit Begleitung durch jeden Rückschlag.
      </>
    }
    featuresLabel="Enthalten sind:"
    features={[
      { text: 'Sechs 1:1-Gespräche' },
      { text: 'Laufende Anpassung des Plans' },
      { text: 'Durchgehende Begleitung' },
      { text: 'Abschlussbericht' },
    ]}
    ctaLabel="Programm Balance buchen"
    ctaHref="#balance"
  />
);

export const Mid = () => (
  <PackageCard
    mid
    tag="Erste Veränderungen zur Gewohnheit machen · 4 Wochen"
    name="Wandel"
    priceLabel="Begleitete Umsetzung"
    price="€399"
    description={
      <>
        <strong>Vier Wochen, in denen aus der Analyse Alltag wird.</strong> Wir bauen
        gemeinsam einen Plan, der auch an vollen Tagen trägt.
      </>
    }
    featuresLabel="Enthalten sind:"
    features={[
      { text: 'Alles aus Klarheit' },
      { text: 'Drei weitere 1:1-Gespräche' },
      { text: 'Begleitung per Nachricht' },
      { text: 'Wochenplan und Tracker' },
    ]}
    ctaLabel="Programm Wandel buchen"
    ctaHref="#wandel"
  />
);

export const TheLadder = () => (
  <PackageGrid>
    <PackageCard
      tag="Standortbestimmung"
      name="Klarheit"
      priceLabel="Individuelle Beratung"
      price="€199"
      description={
        <>
          <strong>Klarheit zeigt dir, wo deine Gesundheit heute steht.</strong> Gemeinsam
          erfassen wir Gewohnheiten und Ziele.
        </>
      }
      featuresLabel="Enthalten sind:"
      features={[
        { text: 'Ausführlicher Fragebogen' },
        { text: 'Persönlicher Bericht' },
        { text: '60-minütiges 1:1-Gespräch' },
      ]}
      ctaLabel="Programm Klarheit buchen"
      ctaHref="#klarheit"
    />
    <PackageCard
      mid
      tag="Veränderung zur Gewohnheit machen · 4 Wochen"
      name="Wandel"
      priceLabel="Begleitete Umsetzung"
      price="€399"
      description={
        <>
          <strong>Vier Wochen, in denen aus der Analyse Alltag wird.</strong> Ein Plan, der
          auch an vollen Tagen trägt.
        </>
      }
      featuresLabel="Enthalten sind:"
      features={[
        { text: 'Alles aus Klarheit' },
        { text: 'Drei weitere 1:1-Gespräche' },
        { text: 'Begleitung per Nachricht' },
      ]}
      ctaLabel="Programm Wandel buchen"
      ctaHref="#wandel"
    />
    <PackageCard
      featured
      tag="Gesundheit im Alltag verankern · 12 Wochen"
      name="Balance"
      priceLabel="Intensive Begleitung"
      price="€899"
      description={
        <>
          <strong>Zwölf Wochen intensive Begleitung.</strong> Verstehen, umsetzen und
          dauerhaft halten.
        </>
      }
      featuresLabel="Enthalten sind:"
      features={[
        { text: 'Sechs 1:1-Gespräche' },
        { text: 'Laufende Anpassung des Plans' },
        { text: 'Abschlussbericht' },
      ]}
      ctaLabel="Programm Balance buchen"
      ctaHref="#balance"
    />
  </PackageGrid>
);
