import type { ReactNode } from 'react';

export interface CredentialChipProps {
  /** A single credential. Lead with its glyph, e.g. "🔬 Dr. rer. nat. in Chemie". */
  children: ReactNode;
  className?: string;
}

/**
 * One credential in the ribbon beneath the hero.
 *
 * @example
 * <CredentialChip>🔬 Dr. rer. nat. in Chemie</CredentialChip>
 */
export function CredentialChip({ children, className = '' }: CredentialChipProps) {
  return <span className={['cred', className].filter(Boolean).join(' ')}>{children}</span>;
}

export interface CredentialRibbonProps {
  children: ReactNode;
  className?: string;
}

/**
 * The row of credential chips. Trust is established here, immediately under the
 * hero — keep it to five or fewer so it stays scannable.
 *
 * @example
 * <CredentialRibbon>
 *   <CredentialChip>🔬 Dr. rer. nat. in Chemie</CredentialChip>
 *   <CredentialChip>🌿 Spezialisiert auf Frauengesundheit</CredentialChip>
 * </CredentialRibbon>
 */
export function CredentialRibbon({ children, className = '' }: CredentialRibbonProps) {
  return (
    <div className={['creds', className].filter(Boolean).join(' ')}>
      <div className="wrap">
        <div className="creds-in">{children}</div>
      </div>
    </div>
  );
}
