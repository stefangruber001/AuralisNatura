import { FaqList, FaqItem, SectionHead } from '@auralis/design-system';

export const TheFaq = () => (
  <div>
    <SectionHead label="Gute Fragen" title="Bevor du buchst." center />
    <FaqList>
      <FaqItem question="Ist das eine medizinische Beratung?" defaultOpen>
        Nein. Auralis Natura ist ganzheitliche Gesundheits- und Ernährungsberatung. Sie
        ersetzt keine ärztliche Diagnose, Behandlung oder Therapie — sie ergänzt sie.
      </FaqItem>
      <FaqItem question="Bist du Ärztin oder Ernährungsberaterin?">
        Nein. Ich bin promovierte Chemikerin (Dr. rer. nat.) mit Weiterbildungen in
        ganzheitlicher Gesundheit, Ernährung und Frauengesundheit.
      </FaqItem>
      <FaqItem question="Was passiert mit meinen Gesundheitsdaten?">
        Sie werden verschlüsselt gespeichert, ausschließlich für deine Begleitung genutzt
        und auf Wunsch jederzeit gelöscht.
      </FaqItem>
      <FaqItem question="Findet die Begleitung online statt?">
        Ja. Alle Gespräche finden per Video statt — von Barcelona aus, weltweit.
      </FaqItem>
    </FaqList>
  </div>
);
