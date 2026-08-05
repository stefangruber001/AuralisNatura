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

const Star = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2l2.4 7.4H22l-6 4.5 2.3 7.1L12 16.6 5.7 21l2.3-7.1-6-4.5h7.6z" />
  </svg>
);

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
export function Testimonial({ quote, name, role, rating, className = '' }: TestimonialProps) {
  return (
    <figure className={['tcard', className].filter(Boolean).join(' ')}>
      {typeof rating === 'number' ? (
        <div className="stars" aria-label={`${rating} out of 5`}>
          {Array.from({ length: rating }, (_, i) => (
            <Star key={i} />
          ))}
        </div>
      ) : null}
      <blockquote>{quote}</blockquote>
      <figcaption className="tperson">
        <span className="av">{name.charAt(0)}</span>
        <span>
          <span className="tn">{name}</span>
          {role ? <span className="tr">{role}</span> : null}
        </span>
      </figcaption>
    </figure>
  );
}
