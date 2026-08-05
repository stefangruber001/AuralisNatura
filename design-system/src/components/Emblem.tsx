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
export function Emblem({ size = 96, watermark = false, className = '' }: EmblemProps) {
  return (
    <span
      className={['emblem', className].filter(Boolean).join(' ')}
      aria-hidden="true"
      style={{ width: size, height: size, display: 'block', opacity: watermark ? 0.07 : 0.92 }}
    />
  );
}
