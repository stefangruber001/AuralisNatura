export interface PhotoFrameProps {
    src: string;
    alt: string;
    /** Intrinsic dimensions — always set them; they prevent layout shift. */
    width?: number;
    height?: number;
    /** Vertical focal point, e.g. "center 22%". Faces sit high in a 4:5 crop. */
    objectPosition?: string;
    className?: string;
}
/**
 * A photograph in the house frame: square corners, soft wide shadow, and a gold
 * hairline inset outside the image. Photography is warm-graded toward the
 * palette before it gets here — never drop in an ungraded image.
 *
 * @example
 * <PhotoFrame src="/images/desiree-portrait.jpg" alt="Dr. rer. nat. Desiree Gruber" width={1122} height={1402} />
 */
export declare function PhotoFrame({ src, alt, width, height, objectPosition, className, }: PhotoFrameProps): import("react").JSX.Element;
