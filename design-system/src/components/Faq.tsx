import { useState, type ReactNode } from 'react';

export interface FaqItemProps {
  question: string;
  children: ReactNode;
  /** Open on first render. Use for the question that removes the biggest doubt. */
  defaultOpen?: boolean;
}

/**
 * One question in the FAQ accordion.
 *
 * @example
 * <FaqItem question="Is this medical advice?">
 *   No. Auralis Natura is holistic health and nutrition coaching.
 * </FaqItem>
 */
export function FaqItem({ question, children, defaultOpen = false }: FaqItemProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={['faq-item', open ? 'open' : ''].filter(Boolean).join(' ')}>
      <button className="faq-q" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span>{question}</span>
        <span className="fq-ic" aria-hidden="true" />
      </button>
      <div className="faq-a">
        <div className="faq-a-in">{children}</div>
      </div>
    </div>
  );
}

export interface FaqListProps {
  children: ReactNode;
  className?: string;
}

/**
 * The accordion wrapper.
 *
 * @example
 * <FaqList><FaqItem question="…">…</FaqItem></FaqList>
 */
export function FaqList({ children, className = '' }: FaqListProps) {
  return <div className={['faq-list', className].filter(Boolean).join(' ')}>{children}</div>;
}
