/**
 * A composed page built only from library components — the reference for how
 * these parts go together. Also the harness used to verify every component
 * renders correctly against the real stylesheet.
 */
import { createRoot } from 'react-dom/client';
import {
  Button, Label, Spark, Emblem,
  Display, Heading, Text, Em, Signature,
  Section, SectionHead,
  PackageCard, PackageGrid,
  Testimonial,
  CredentialChip, CredentialRibbon,
  CtaCard, PhotoFrame,
  FaqItem, FaqList,
  MetaList, ImageBand,
} from '../src/index';

function Demo() {
  return (
    <>
      <Section>
        <Label kicker>Auralis Natura</Label>
        <Display>
          Understand your body. <Em>Improve your health for good.</Em>
        </Display>
        <Text variant="lead">
          Science-based health coaching for people who want to improve their health
          holistically and for the long term.
        </Text>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 24 }}>
          <Button variant="clay" size="lg" arrow subLabel="free, no obligation">
            Book an intro call
          </Button>
          <Button variant="ghost" size="lg">See how it works</Button>
          <Button variant="forest">Free intro call</Button>
        </div>
        <div style={{ display: 'flex', gap: 30, alignItems: 'center', marginTop: 34 }}>
          <Spark />
          <Emblem size={64} />
        </div>
      </Section>

      <CredentialRibbon>
        <CredentialChip>🔬 Dr. rer. nat. in Chemistry</CredentialChip>
        <CredentialChip>🧬 15+ years of research</CredentialChip>
        <CredentialChip>🌿 Specialist in women’s health</CredentialChip>
      </CredentialRibbon>

      <Section tone="dark">
        <Label onDark>Why Auralis</Label>
        <Heading level={2}>
          Your body is sending signals.<br />
          <Em>Let’s find out what’s behind them.</Em>
        </Heading>
        <Text variant="lead">
          You don’t need more pressure, more rules or more discipline.{' '}
          <strong>This isn’t about the next diet.</strong> It’s about shaping the way you eat.
        </Text>
      </Section>

      <Section>
        <SectionHead
          label="Ways to work together"
          title={<>Understand. Change. Keep going.</>}
          sub="Every path starts with a free intro call."
        />
        <PackageGrid>
          <PackageCard
            tag="Where you stand & health analysis"
            name="Clarity"
            priceLabel="One-to-one consultation"
            price="€199"
            description={<><strong>Clarity shows you where your health stands today.</strong> We map your habits, your circumstances and your goals together.</>}
            featuresLabel="What’s included:"
            features={[{ text: 'In-depth health questionnaire' }, { text: 'Personal written report' }, { text: '60-minute 1:1 session' }]}
            ctaLabel="Book Clarity program"
            ctaHref="#"
          />
          <PackageCard
            mid
            tag="Turn first changes into habits · 4 weeks"
            name="Change"
            priceLabel="Guided implementation"
            price="€399"
            description={<><strong>A four-week programme that takes you from analysis to action.</strong> We build a plan that holds up in real life.</>}
            featuresLabel="What’s included:"
            features={[{ text: 'Everything in Clarity' }, { text: 'Three further 1:1 sessions' }, { text: 'Message support throughout' }]}
            ctaLabel="Book Change program"
            ctaHref="#"
          />
          <PackageCard
            featured
            tag="Make health part of daily life · 12 weeks"
            name="Balance"
            priceLabel="In-depth guidance"
            price="€899"
            description={<><strong>Twelve weeks of in-depth guidance.</strong> Understand, put into practice, and make it last.</>}
            featuresLabel="What’s included:"
            features={[{ text: 'Six 1:1 sessions' }, { text: 'Ongoing plan adjustment' }, { text: 'Closing report' }]}
            ctaLabel="Book Balance program"
            ctaHref="#"
          />
        </PackageGrid>
      </Section>

      <ImageBand
        src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1200' height='600'%3E%3Crect width='1200' height='600' fill='%235A3A22'/%3E%3C/svg%3E"
        alt="Placeholder band"
        label="The approach"
        caption="Rigorous science. Personal guidance."
      />

      <Section>
        <div style={{ display: 'grid', gridTemplateColumns: '.82fr 1.18fr', gap: 60, alignItems: 'start' }}>
          <div>
            <PhotoFrame
              src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='1000'%3E%3Crect width='800' height='1000' fill='%23DAC79E'/%3E%3C/svg%3E"
              alt="Portrait placeholder"
              width={800}
              height={1000}
            />
            <div style={{ textAlign: 'center', padding: '6px 0 4px' }}>
              <Emblem size={96} />
              <p className="about-quote">Rigorous science. Personal guidance.</p>
            </div>
            <MetaList
              entries={[
                { term: 'Scientific background', value: 'Dr. rer. nat. in Chemistry' },
                { term: 'Professional experience', value: 'More than fifteen years in research' },
                { term: 'Areas of focus', value: 'Holistic health · Nutrition · Women’s health' },
                { term: 'Based in', value: 'Barcelona · Online worldwide' },
              ]}
            />
          </div>
          <div>
            <Label kicker>The founder</Label>
            <Heading level={2}>Understand the body. <Em>See the person.</Em></Heading>
            <Text variant="big">
              Auralis Natura began with a simple conviction: good health needs solid science,
              and it needs time, listening and trust.
            </Text>
            <Text>
              I’m Desiree Gruber, a chemist with a doctorate. More than fifteen years in research
              shaped the way I work: precise, structured, evidence-based.
            </Text>
            <Signature role="Founder · Auralis Natura — Holistic Health">Desiree Gruber</Signature>
          </div>
        </div>
      </Section>

      <Section tone="dark">
        <Label onDark>In their words</Label>
        <Heading level={2}>Quietly, life starts to feel lighter.</Heading>
        <div className="tmt-grid" style={{ marginTop: 28 }}>
          <Testimonial
            rating={5}
            quote="Thanks to her expert, individual guidance I’ve changed the way I eat for good. I have noticeably more energy day to day."
            name="Rebecca E."
            role="Balance · Hausmannstätten"
          />
          <Testimonial
            rating={5}
            quote="The analysis was a real turning point. The changes fitted into my days without any effort."
            name="Helmut P."
            role="Change · Graz, Austria"
          />
        </div>
      </Section>

      <Section>
        <SectionHead label="Good questions" title="Before you book." center />
        <FaqList>
          <FaqItem question="Is this medical advice?" defaultOpen>
            No. Auralis Natura is holistic health and nutrition coaching. It does not replace
            medical diagnosis, treatment or therapy.
          </FaqItem>
          <FaqItem question="Are you a doctor or a registered dietitian?">
            No. I’m a chemist with a doctorate (Dr. rer. nat.) with further training in holistic
            health, nutrition and women’s health.
          </FaqItem>
        </FaqList>
      </Section>

      <CtaCard
        label="Free & no obligation"
        title={<>Book your free<br /> intro call.</>}
        body="In a calm conversation with no obligation, we look at where you are right now."
      />
    </>
  );
}

createRoot(document.getElementById('root')!).render(<Demo />);
