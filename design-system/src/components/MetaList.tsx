export interface MetaEntry {
  /** The field name, set in small uppercase, e.g. "Scientific background". */
  term: string;
  /** The value, right-aligned. */
  value: string;
}

export interface MetaListProps {
  entries: MetaEntry[];
  className?: string;
}

/**
 * The credentials table — quiet, factual, and the page's main trust device.
 * Facts only: every line must be verifiable.
 *
 * @example
 * <MetaList entries={[
 *   { term: 'Scientific background', value: 'Dr. rer. nat. in Chemistry' },
 *   { term: 'Professional experience', value: 'More than fifteen years in research' },
 * ]} />
 */
export function MetaList({ entries, className = '' }: MetaListProps) {
  return (
    <dl className={['about-meta', className].filter(Boolean).join(' ')}>
      {entries.map((e, i) => (
        <div key={i}>
          <dt>{e.term}</dt>
          <dd>{e.value}</dd>
        </div>
      ))}
    </dl>
  );
}
