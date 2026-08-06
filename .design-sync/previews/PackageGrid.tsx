import { PackageGrid, PackageCard } from '@auralis/design-system';

const de = [
  {
    tag: 'Standortbestimmung',
    name: 'Klarheit',
    priceLabel: 'Individuelle Beratung',
    price: '€199',
    description: (
      <>
        <strong>Klarheit zeigt dir, wo deine Gesundheit heute steht.</strong> Gemeinsam
        erfassen wir Gewohnheiten und Ziele.
      </>
    ),
    featuresLabel: 'Enthalten sind:',
    features: [
      { text: 'Ausführlicher Fragebogen' },
      { text: 'Persönlicher Bericht' },
      { text: '60-minütiges 1:1-Gespräch' },
    ],
    ctaLabel: 'Programm Klarheit buchen',
    ctaHref: '#klarheit',
  },
  {
    mid: true,
    tag: 'Veränderung zur Gewohnheit machen · 4 Wochen',
    name: 'Wandel',
    priceLabel: 'Begleitete Umsetzung',
    price: '€399',
    description: (
      <>
        <strong>Vier Wochen, in denen aus der Analyse Alltag wird.</strong> Ein Plan, der
        auch an vollen Tagen trägt.
      </>
    ),
    featuresLabel: 'Enthalten sind:',
    features: [
      { text: 'Alles aus Klarheit' },
      { text: 'Drei weitere 1:1-Gespräche' },
      { text: 'Begleitung per Nachricht' },
    ],
    ctaLabel: 'Programm Wandel buchen',
    ctaHref: '#wandel',
  },
  {
    featured: true,
    tag: 'Gesundheit im Alltag verankern · 12 Wochen',
    name: 'Balance',
    priceLabel: 'Intensive Begleitung',
    price: '€899',
    description: (
      <>
        <strong>Zwölf Wochen intensive Begleitung.</strong> Verstehen, umsetzen und
        dauerhaft halten.
      </>
    ),
    featuresLabel: 'Enthalten sind:',
    features: [
      { text: 'Sechs 1:1-Gespräche' },
      { text: 'Laufende Anpassung des Plans' },
      { text: 'Abschlussbericht' },
    ],
    ctaLabel: 'Programm Balance buchen',
    ctaHref: '#balance',
  },
];

const en = [
  {
    tag: 'Where you stand',
    name: 'Clarity',
    priceLabel: 'One-to-one consultation',
    price: '€199',
    description: (
      <>
        <strong>Clarity shows you where your health stands today.</strong> We map your
        habits and your goals together.
      </>
    ),
    featuresLabel: 'What’s included:',
    features: [
      { text: 'In-depth questionnaire' },
      { text: 'Personal written report' },
      { text: '60-minute 1:1 session' },
    ],
    ctaLabel: 'Book Clarity program',
    ctaHref: '#clarity',
  },
  {
    mid: true,
    tag: 'Turn change into habit · 4 weeks',
    name: 'Change',
    priceLabel: 'Guided implementation',
    price: '€399',
    description: (
      <>
        <strong>Four weeks that turn analysis into everyday life.</strong> A plan that holds
        up on full days.
      </>
    ),
    featuresLabel: 'What’s included:',
    features: [
      { text: 'Everything in Clarity' },
      { text: 'Three further 1:1 sessions' },
      { text: 'Message support throughout' },
    ],
    ctaLabel: 'Book Change program',
    ctaHref: '#change',
  },
  {
    featured: true,
    tag: 'Make health part of daily life · 12 weeks',
    name: 'Balance',
    priceLabel: 'In-depth guidance',
    price: '€899',
    description: (
      <>
        <strong>Twelve weeks of in-depth guidance.</strong> Understand, put into practice,
        make it last.
      </>
    ),
    featuresLabel: 'What’s included:',
    features: [
      { text: 'Six 1:1 sessions' },
      { text: 'Ongoing plan adjustment' },
      { text: 'Closing report' },
    ],
    ctaLabel: 'Book Balance program',
    ctaHref: '#balance',
  },
];

export const TheLadder = () => (
  <PackageGrid>
    {de.map((p) => (
      <PackageCard key={p.name} {...p} />
    ))}
  </PackageGrid>
);

export const English = () => (
  <PackageGrid>
    {en.map((p) => (
      <PackageCard key={p.name} {...p} />
    ))}
  </PackageGrid>
);
