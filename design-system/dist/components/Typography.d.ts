import type { ReactNode, ElementType } from 'react';
export interface DisplayProps {
    children: ReactNode;
    as?: ElementType;
    className?: string;
}
/**
 * The largest editorial voice — Fraunces, used once per page for the hero.
 *
 * @example
 * <Display>Understand your body. <Em>Improve your health for good.</Em></Display>
 */
export declare function Display({ children, as: Tag, className }: DisplayProps): import("react").JSX.Element;
export interface HeadingProps {
    children: ReactNode;
    /** 2 is the section heading; 3 is a card title. */
    level?: 2 | 3;
    as?: ElementType;
    className?: string;
}
/**
 * Section and card headings.
 *
 * @example
 * <Heading level={2}>Your body is sending signals.</Heading>
 */
export declare function Heading({ children, level, as, className }: HeadingProps): import("react").JSX.Element;
export interface TextProps {
    children: ReactNode;
    /** `lead` opens a section; `big` is the emphasised opening paragraph. */
    variant?: 'body' | 'lead' | 'big';
    className?: string;
}
/**
 * Body copy.
 *
 * @example
 * <Text variant="lead">Every path starts with a free intro call.</Text>
 */
export declare function Text({ children, variant, className }: TextProps): import("react").JSX.Element;
export interface EmProps {
    children: ReactNode;
    className?: string;
}
/**
 * The brand's second voice: italic cinnamon-rust on light surfaces, amber on dark bands.
 * Use it for the turn in a headline — never for a whole paragraph.
 *
 * @example
 * <Heading>Understand the body. <Em>See the person.</Em></Heading>
 */
export declare function Em({ children, className }: EmProps): import("react").JSX.Element;
export interface SignatureProps {
    children: ReactNode;
    role?: string;
    className?: string;
}
/**
 * The founder's hand-signed sign-off at the end of the About section.
 *
 * @example
 * <Signature role="Founder · Auralis Natura">Desiree Gruber</Signature>
 */
export declare function Signature({ children, role, className }: SignatureProps): import("react").JSX.Element;
