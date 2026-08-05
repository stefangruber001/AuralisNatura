export interface SparkProps {
  /** Larger variant used as a standalone section ornament. */
  large?: boolean;
  className?: string;
}

/**
 * The three-dot ornament — clay, gold, sage. The brand's quietest signature;
 * use it to punctuate, never to decorate every block.
 *
 * @example
 * <Spark />
 */
export function Spark({ large = false, className = '' }: SparkProps) {
  const cls = ['spark', large ? 'spark-lg' : '', className].filter(Boolean).join(' ');
  return (
    <span className={cls} aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
  );
}
