export interface EmblemProps {
    /** Rendered size in pixels. 96 in the About column, 30 in the app bar. */
    size?: number;
    /** Faint watermark treatment, as used behind the dark bands. */
    watermark?: boolean;
    className?: string;
}
/**
 * The botanical seal — the recurring brand mark.
 *
 * @example
 * <Emblem size={96} />
 * @example
 * <Emblem size={220} watermark />
 */
export declare function Emblem({ size, watermark, className }: EmblemProps): import("react").JSX.Element;
