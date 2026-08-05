import type { ReactNode } from 'react';
export type ButtonVariant = 'clay' | 'forest' | 'ghost';
export type ButtonSize = 'md' | 'lg';
export interface ButtonProps {
    /** Label text. */
    children: ReactNode;
    /**
     * `clay` is the action colour and the default — use it for the one primary
     * action on a surface. `forest` is the dark nav/header button. `ghost` is the
     * quiet secondary. Never use more than one `clay` button in a single view.
     */
    variant?: ButtonVariant;
    size?: ButtonSize;
    /** Renders the diagonal arrow used on the site's primary calls to action. */
    arrow?: boolean;
    /**
     * Quiet second line inside the button, e.g. "kostenlos und unverbindlich".
     * Use it to remove risk at the moment of clicking, not for extra marketing.
     */
    subLabel?: string;
    href?: string;
    onClick?: () => void;
    /** Opens in a new tab; only meaningful with `href`. */
    external?: boolean;
    className?: string;
}
/**
 * The primary interactive element.
 *
 * @example
 * <Button variant="clay" size="lg" arrow subLabel="free, no obligation">
 *   Book an intro call
 * </Button>
 *
 * @example
 * <Button variant="ghost" href="#services">See how it works</Button>
 */
export declare function Button({ children, variant, size, arrow, subLabel, href, onClick, external, className, }: ButtonProps): import("react").JSX.Element;
