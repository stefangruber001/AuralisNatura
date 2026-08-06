import { Signature, Text } from '@auralis/design-system';

export const Default = () => (
  <Signature role="Gründerin · Auralis Natura — Holistic Health">Desiree Gruber</Signature>
);

export const ClosingTheAboutSection = () => (
  <div style={{ maxWidth: 620 }}>
    <Text>
      Was ich anbiete, ist keine Behandlung. Es ist Begleitung: verständlich erklärt,
      wissenschaftlich eingeordnet und auf dein Leben zugeschnitten.
    </Text>
    <Signature role="Gründerin · Auralis Natura — Holistic Health">Desiree Gruber</Signature>
  </div>
);

export const NameOnly = () => <Signature>Desiree Gruber</Signature>;
