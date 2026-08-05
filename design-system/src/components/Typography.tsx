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
export function Display({ children, as: Tag = 'h1', className = '' }: DisplayProps) {
  return <Tag className={['display', className].filter(Boolean).join(' ')}>{children}</Tag>;
}

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
export function Heading({ children, level = 2, as, className = '' }: HeadingProps) {
  const Tag = (as ?? (level === 2 ? 'h2' : 'h3')) as ElementType;
  return <Tag className={[`h${level}`, className].filter(Boolean).join(' ')}>{children}</Tag>;
}

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
export function Text({ children, variant = 'body', className = '' }: TextProps) {
  const cls = [variant === 'body' ? '' : variant, className].filter(Boolean).join(' ');
  return <p className={cls || undefined}>{children}</p>;
}

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
export function Em({ children, className = '' }: EmProps) {
  return <span className={['em', className].filter(Boolean).join(' ')}>{children}</span>;
}

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
export function Signature({ children, role, className = '' }: SignatureProps) {
  return (
    <div className={className || undefined}>
      <div className="sig">{children}</div>
      {role ? <span>{role}</span> : null}
    </div>
  );
}
