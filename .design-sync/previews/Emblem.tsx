import { Emblem } from '@auralis/design-system';

export const Sizes = () => (
  <div style={{ display: 'flex', gap: 28, alignItems: 'flex-end' }}>
    <Emblem size={96} />
    <Emblem size={54} />
    <Emblem size={30} />
  </div>
);

export const SigningABlock = () => (
  <div style={{ textAlign: 'center', maxWidth: 320 }}>
    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
      <Emblem size={96} />
    </div>
    <p className="about-quote">Fundierte Wissenschaft. Persönliche Begleitung.</p>
  </div>
);

export const Watermark = () => (
  <div style={{ display: 'flex', gap: 40, alignItems: 'center', background: 'var(--paper-2)', padding: 30 }}>
    <Emblem size={180} watermark />
    <Emblem size={180} />
  </div>
);
