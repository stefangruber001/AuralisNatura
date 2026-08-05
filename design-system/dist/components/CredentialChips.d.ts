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
export declare function CredentialChip({ children, className }: CredentialChipProps): import("react").JSX.Element;
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
export declare function CredentialRibbon({ children, className }: CredentialRibbonProps): import("react").JSX.Element;
