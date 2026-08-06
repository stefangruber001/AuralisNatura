import { MetaList } from '@auralis/design-system';

export const Credentials = () => (
  <div style={{ maxWidth: 460 }}>
    <MetaList
      entries={[
        { term: 'Wissenschaftlicher Hintergrund', value: 'Dr. rer. nat. in Chemie' },
        { term: 'Berufserfahrung', value: 'Mehr als fünfzehn Jahre in der Forschung' },
        { term: 'Schwerpunkte', value: 'Ganzheitliche Gesundheit · Frauengesundheit' },
        { term: 'Standort', value: 'Barcelona · Online weltweit' },
        { term: 'Sprachen', value: 'Deutsch · English · Español' },
      ]}
    />
  </div>
);

export const English = () => (
  <div style={{ maxWidth: 460 }}>
    <MetaList
      entries={[
        { term: 'Scientific background', value: 'Dr. rer. nat. in Chemistry' },
        { term: 'Professional experience', value: 'More than fifteen years in research' },
        { term: 'Based in', value: 'Barcelona · Online worldwide' },
      ]}
    />
  </div>
);
