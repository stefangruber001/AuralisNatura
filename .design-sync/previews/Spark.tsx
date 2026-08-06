import { Spark, Heading } from '@auralis/design-system';

export const Default = () => <Spark />;

export const Large = () => <Spark large />;

export const PunctuatingASection = () => (
  <div style={{ textAlign: 'center', maxWidth: 480 }}>
    <Heading level={3}>Fundierte Wissenschaft.</Heading>
    <div style={{ display: 'flex', justifyContent: 'center', margin: '18px 0' }}>
      <Spark large />
    </div>
    <p className="lead" style={{ margin: 0 }}>
      Persönliche Begleitung.
    </p>
  </div>
);
