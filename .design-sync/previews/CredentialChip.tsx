import { CredentialChip } from '@auralis/design-system';

export const Single = () => <CredentialChip>🔬 Dr. rer. nat. in Chemie</CredentialChip>;

export const TheSet = () => (
  <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', alignItems: 'center' }}>
    <CredentialChip>🔬 Dr. rer. nat. in Chemie</CredentialChip>
    <CredentialChip>🧬 15+ Jahre Forschung und Pharmaindustrie</CredentialChip>
    <CredentialChip>🥗 Ganzheitliche Ernährungsberatung</CredentialChip>
    <CredentialChip>🌿 Spezialisiert auf Frauengesundheit</CredentialChip>
    <CredentialChip>🧘 Yoga- und Meditationslehrerin</CredentialChip>
  </div>
);
