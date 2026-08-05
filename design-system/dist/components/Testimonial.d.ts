import type { ReactNode } from 'react';
export interface TestimonialProps {
    /** The review, in the client's own words. Never edit meaning — trim only. */
    quote: ReactNode;
    /** Display name, e.g. "Rebecca E.". */
    name: string;
    /** Programme and place, e.g. "Balance · Hausmannstätten". */
    role?: string;
    /** Star rating, 0–5. Omit rather than invent one. */
    rating?: number;
    className?: string;
}
/**
 * A client review on the dark testimonial band.
 *
 * Only ever render genuine reviews — fabricated testimonials are a hard
 * guardrail for this brand, not a style preference.
 *
 * @example
 * <Testimonial
 *   rating={5}
 *   quote="Dank ihrer kompetenten Beratung habe ich meine Ernährung nachhaltig umgestellt."
 *   name="Rebecca E."
 *   role="Balance · Hausmannstätten"
 * />
 */
export declare function Testimonial({ quote, name, role, rating, className }: TestimonialProps): import("react").JSX.Element;
