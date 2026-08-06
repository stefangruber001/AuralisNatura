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
     * Inverts the card to the dark brown band — the top of the ladder.
     * Use on at most one card in a row.
     */
    featured?: boolean;
    /**
     * The warm sand middle treatment. On the production ladder the three cards
     * step light → sand → dark, so the middle card carries this.
     */
    mid?: boolean;
    className?: string;
}
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
export declare function PackageCard({ tag, name, priceLabel, price, description, featuresLabel, features, ctaLabel, ctaHref, onCta, featured, mid, className, }: PackageCardProps): import("react").JSX.Element;
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
export declare function PackageGrid({ children, className }: PackageGridProps): import("react").JSX.Element;
