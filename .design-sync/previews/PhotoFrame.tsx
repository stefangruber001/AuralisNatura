import { PhotoFrame, MetaList, Emblem, Label, Heading, Text, Em, Signature } from '@auralis/design-system';
import { portrait, portraitTall } from './_assets';

export const Portrait = () => (
  <div style={{ maxWidth: 340 }}>
    <PhotoFrame
      src={portrait}
      alt="Dr. rer. nat. Desiree Gruber an ihrem Schreibtisch"
      width={440}
      height={550}
    />
  </div>
);

/* The frame is always 4:5, so a taller source gets cropped — objectPosition
   decides which part survives. Same image, two focal points. */
export const FocalPoint = () => (
  <div style={{ display: 'flex', gap: 26 }}>
    <div style={{ width: 240 }}>
      <PhotoFrame
        src={portraitTall}
        alt="Desiree Gruber, Fokus auf das Gesicht"
        width={420}
        height={630}
        objectPosition="center 0%"
      />
      <p className="soon-note" style={{ marginTop: 12 }}>objectPosition="center 0%"</p>
    </div>
    <div style={{ width: 240 }}>
      <PhotoFrame
        src={portraitTall}
        alt="Desiree Gruber, Fokus auf den Schreibtisch"
        width={420}
        height={630}
        objectPosition="center 100%"
      />
      <p className="soon-note" style={{ marginTop: 12 }}>objectPosition="center 100%"</p>
    </div>
  </div>
);

export const InTheAboutColumn = () => (
  <div style={{ display: 'grid', gridTemplateColumns: '.82fr 1.18fr', gap: 44, alignItems: 'start' }}>
    <div>
      <PhotoFrame src={portrait} alt="Dr. rer. nat. Desiree Gruber" width={440} height={550} />
      <div style={{ textAlign: 'center', padding: '14px 0 4px' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
          <Emblem size={64} />
        </div>
        <p className="about-quote">Fundierte Wissenschaft. Persönliche Begleitung.</p>
      </div>
      <MetaList
        entries={[
          { term: 'Hintergrund', value: 'Dr. rer. nat. in Chemie' },
          { term: 'Standort', value: 'Barcelona · Online' },
        ]}
      />
    </div>
    <div>
      <Label kicker>Die Gründerin</Label>
      <Heading level={2}>
        Den Körper verstehen. <Em>Den Menschen sehen.</Em>
      </Heading>
      <Text variant="big">
        Auralis Natura ist aus einer einfachen Überzeugung entstanden: Gute Gesundheit
        braucht solide Wissenschaft — und sie braucht Zeit, Zuhören und Vertrauen.
      </Text>
      <Signature role="Gründerin · Auralis Natura — Holistic Health">Desiree Gruber</Signature>
    </div>
  </div>
);
