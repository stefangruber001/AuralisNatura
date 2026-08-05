import { type ReactNode } from 'react';
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
export declare function FaqItem({ question, children, defaultOpen }: FaqItemProps): import("react").JSX.Element;
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
export declare function FaqList({ children, className }: FaqListProps): import("react").JSX.Element;
