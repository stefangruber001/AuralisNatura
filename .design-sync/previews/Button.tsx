import { Button } from '@auralis/design-system';

export const Primary = () => (
  <Button variant="clay" size="lg" arrow subLabel="kostenlos und unverbindlich">
    Kostenloses Gespräch buchen
  </Button>
);

export const Variants = () => (
  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
    <Button variant="clay">Programm Klarheit buchen</Button>
    <Button variant="forest">Kostenloses Gespräch</Button>
    <Button variant="ghost">So funktioniert es</Button>
  </div>
);

export const Sizes = () => (
  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
    <Button variant="clay">Jetzt buchen</Button>
    <Button variant="clay" size="lg" arrow>
      Jetzt buchen
    </Button>
  </div>
);

export const PairedInAHero = () => (
  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
    <Button variant="clay" size="lg" arrow subLabel="kostenlos und unverbindlich">
      Kostenloses Gespräch buchen
    </Button>
    <Button variant="ghost" size="lg" href="#services">
      So funktioniert es
    </Button>
  </div>
);
