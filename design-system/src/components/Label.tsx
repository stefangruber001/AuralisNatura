import type { ReactNode } from 'react';

export interface LabelProps {
  children: ReactNode;
  /** Adds the short gold rule that marks a section kicker. */
  kicker?: boolean;
  /** Use on the dark brown bands, where the label switches to warm sand. */
  onDark?: boolean;
  className?: string;
}

/**
 * The small uppercase, wide-tracked label that opens a section or annotates a value.
 * Clay on light surfaces; sand on the dark bands.
 *
 * @example
 * <Label kicker>The founder</Label>
 *
 * @example
 * <Label onDark>Ways to work together</Label>
 */
export function Label({ children, kicker = false, onDark = false, className = '' }: LabelProps) {
  /* label--cream is the stylesheet's own dark-band treatment: it recolours the
     text AND swaps the leaf glyph to sand, which an inline colour cannot. */
  const cls = ['label', kicker ? 'u-kick' : '', onDark ? 'label--cream' : '', className]
    .filter(Boolean)
    .join(' ');
  return <span className={cls}>{children}</span>;
}
