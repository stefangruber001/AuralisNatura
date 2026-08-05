import type { ReactNode } from 'react';

export interface PackageFeature {
  /** One included item. Keep to a single line — the list is scanned, not read. */
  text: string;
}

export interface PackageCardProps {
  /** Small tag above the name, e.g. "Standortbestimmung & Gesundheitsanalyse". */
  tag?: string;
  /** The package name: Klarheit · Wandel · Balance. */
  name: string;
  /** Quiet label above the price, e.g. "Individuelle Beratung". */
  priceLabel?: string;
  /** Formatted price including the currency symbol, e.g. "€199". */
  price: string;
  /**
   * The pitch. Lead with one bolded sentence — the site wraps the first sentence
   * in <strong> so the scanner gets the promise before the detail.
   */
  description: ReactNode;
  /** Heading above the list, e.g. "Enthalten sind:". */
  featuresLabel?: string;
  features?: PackageFeature[];
  ctaLabel: string;
  ctaHref?: string;
  onCta?: () => void;
  /**
   * Marks the most-chosen package: inverts the card to the dark brown band.
   * Use on at most one card in a row.
   */
  featured?: boolean;
  className?: string;
}

const Check = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
    <path d="M5 12l5 5L20 6" />
  </svg>
);

/**
 * A pricing card — the commercial heart of the page.
 *
 * @example
 * <PackageCard
 *   tag="Standortbestimmung & Gesundheitsanalyse"
 *   name="Klarheit"
 *   priceLabel="Individuelle Beratung"
 *   price="€199"
 *   description={<><strong>Klarheit zeigt dir, wo deine Gesundheit heute steht.</strong> Gemeinsam erfassen wir deine Gewohnheiten und Ziele.</>}
 *   featuresLabel="Enthalten sind:"
 *   features={[{ text: 'Ausführlicher Fragebogen' }, { text: 'Persönlicher Bericht' }]}
 *   ctaLabel="Programm Klarheit buchen"
 *   ctaHref="https://book.stripe.com/…"
 * />
 */
export function PackageCard({
  tag,
  name,
  priceLabel,
  price,
  description,
  featuresLabel,
  features = [],
  ctaLabel,
  ctaHref,
  onCta,
  featured = false,
  className = '',
}: PackageCardProps) {
  const cls = ['pkg', featured ? 'feat' : '', className].filter(Boolean).join(' ');
  return (
    <article className={cls}>
      {tag ? <span className="pk-tag">{tag}</span> : null}
      <h3>{name}</h3>
      <div className="pk-price">
        {priceLabel ? <span className="from">{priceLabel}</span> : null}
        {price}
      </div>
      <p className="pk-desc">{description}</p>
      {featuresLabel ? <p className="pk-incl">{featuresLabel}</p> : null}
      {features.length ? (
        <ul>
          {features.map((f, i) => (
            <li key={i}>
              <Check />
              <span>{f.text}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {ctaHref ? (
        <a className={`btn ${featured ? 'btn-clay' : 'btn-ghost'}`} href={ctaHref}>
          {ctaLabel}
        </a>
      ) : (
        <button type="button" className={`btn ${featured ? 'btn-clay' : 'btn-ghost'}`} onClick={onCta}>
          {ctaLabel}
        </button>
      )}
    </article>
  );
}

export interface PackageGridProps {
  children: ReactNode;
  className?: string;
}

/**
 * The row that holds package cards — three across on desktop, stacking on mobile.
 *
 * @example
 * <PackageGrid><PackageCard … /><PackageCard … /></PackageGrid>
 */
export function PackageGrid({ children, className = '' }: PackageGridProps) {
  return <div className={['pkgs', className].filter(Boolean).join(' ')}>{children}</div>;
}
