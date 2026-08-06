import { FaqItem, FaqList } from '@auralis/design-system';

export const Open = () => (
  <FaqList>
    <FaqItem question="Ist das eine medizinische Beratung?" defaultOpen>
      Nein. Auralis Natura ist ganzheitliche Gesundheits- und Ernährungsberatung. Sie
      ersetzt keine ärztliche Diagnose, Behandlung oder Therapie — sie ergänzt sie.
    </FaqItem>
  </FaqList>
);

export const Closed = () => (
  <FaqList>
    <FaqItem question="Bist du Ärztin oder Ernährungsberaterin?">
      Nein. Ich bin promovierte Chemikerin (Dr. rer. nat.) mit Weiterbildungen in
      ganzheitlicher Gesundheit, Ernährung und Frauengesundheit.
    </FaqItem>
  </FaqList>
);
