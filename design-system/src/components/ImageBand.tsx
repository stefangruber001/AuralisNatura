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
export function ImageBand({ src, alt, caption, label, hero = false, className = '' }: ImageBandProps) {
  const cls = ['img-band', hero ? 'img-band--hero' : '', className].filter(Boolean).join(' ');
  return (
    <div className={cls}>
      <img src={src} alt={alt} loading="lazy" decoding="async" />
      {caption || label ? (
        <div className="img-cap">
          {label ? <span className="label">{label}</span> : null}
          {caption ? <p>{caption}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
