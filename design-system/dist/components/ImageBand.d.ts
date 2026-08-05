import type { ReactNode } from 'react';
export interface ImageBandProps {
    src: string;
    alt: string;
    /** Overlaid caption — one editorial sentence, never a paragraph. */
    caption?: ReactNode;
    label?: string;
    /** Taller variant for a hero-scale band. */
    hero?: boolean;
    className?: string;
}
/**
 * A full-bleed photographic band with an optional caption plate. Use it to let
 * the page breathe between dense sections.
 *
 * @example
 * <ImageBand
 *   src="/images/nourish.jpg"
 *   alt="A table of vegetables and a notebook"
 *   label="The approach"
 *   caption="Rigorous science. Personal guidance."
 * />
 */
export declare function ImageBand({ src, alt, caption, label, hero, className }: ImageBandProps): import("react").JSX.Element;
