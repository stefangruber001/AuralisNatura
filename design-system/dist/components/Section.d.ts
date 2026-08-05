import type { ReactNode } from 'react';
export interface SectionProps {
    children: ReactNode;
    /**
     * `paper` is the default light surface. `dark` is the brown gradient band used
     * for the emotional turns of the page — use it sparingly, three or four times
     * at most, or it stops feeling like a change of register.
     */
    tone?: 'paper' | 'cream' | 'dark';
    /** Vertical rhythm. `sm` for tighter interstitial sections. */
    padding?: 'sm' | 'md';
    id?: string;
    className?: string;
}
/**
 * A full-width page section, with the site's vertical rhythm and max-width wrap.
 *
 * @example
 * <Section tone="dark" id="problem">
 *   <Heading level={2}>Dein Körper sendet Signale.</Heading>
 * </Section>
 */
export declare function Section({ children, tone, padding, id, className, }: SectionProps): import("react").JSX.Element;
export interface SectionHeadProps {
    /** The small uppercase kicker above the title. */
    label?: string;
    title: ReactNode;
    /** Optional lead paragraph beneath the title. */
    sub?: ReactNode;
    /** Centres the block — used for the certificates and FAQ heads. */
    center?: boolean;
    onDark?: boolean;
    className?: string;
}
/**
 * The standard section opening: kicker, title, optional lead.
 *
 * @example
 * <SectionHead label="Qualifications" title="Qualifications & certificates." center />
 */
export declare function SectionHead({ label, title, sub, center, onDark, className, }: SectionHeadProps): import("react").JSX.Element;
