import type { ReactNode } from 'react';

export interface CtaCardProps {
  label?: string;
  title: ReactNode;
  body?: ReactNode;
  /** Right-hand column — typically a booking widget or form. */
  aside?: ReactNode;
  className?: string;
}

/**
 * The closing dark card that ends the page. One per page: it is the final ask,
 * and it loses all force if repeated.
 *
 * @example
 * <CtaCard
 *   label="Free & no obligation"
 *   title={<>Book your free<br /> intro call.</>}
 *   body="In a calm conversation with no obligation, we look at where you are."
 * />
 */
export function CtaCard({ label, title, body, aside, className = '' }: CtaCardProps) {
  return (
    <section className={['cta', 'sec-pad', className].filter(Boolean).join(' ')}>
      <div className="wrap">
        <div className="cta-card">
          <span className="emblem cta-wm" aria-hidden="true" />
          <div className="cta-grid">
            <div>
              {label ? <span className="label">{label}</span> : null}
              <h3 className="h2">{title}</h3>
              {body ? <p>{body}</p> : null}
            </div>
            {aside ? <div>{aside}</div> : null}
          </div>
        </div>
      </div>
    </section>
  );
}
