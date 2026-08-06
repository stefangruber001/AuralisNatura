// src/components/Button.tsx
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
function Button({
  children,
  variant = "clay",
  size = "md",
  arrow = false,
  subLabel,
  href,
  onClick,
  external = false,
  className = ""
}) {
  const variantClass = {
    clay: "btn-clay",
    forest: "btn-primary",
    ghost: "btn-ghost"
  }[variant];
  const classes = [
    "btn",
    variantClass,
    size === "lg" ? "btn-lg" : "",
    arrow ? "btn-arrow" : "",
    className
  ].filter(Boolean).join(" ");
  const inner = /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs("span", { children: [
      children,
      subLabel ? /* @__PURE__ */ jsx("span", { className: "btn-sub", children: subLabel }) : null
    ] }),
    arrow ? /* @__PURE__ */ jsx("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, "aria-hidden": "true", children: /* @__PURE__ */ jsx("path", { d: "M7 17L17 7M17 7H8M17 7v9" }) }) : null
  ] });
  if (href) {
    return /* @__PURE__ */ jsx(
      "a",
      {
        className: classes,
        href,
        ...external ? { target: "_blank", rel: "noopener noreferrer" } : {},
        children: inner
      }
    );
  }
  return /* @__PURE__ */ jsx("button", { type: "button", className: classes, onClick, children: inner });
}

// src/components/Label.tsx
import { jsx as jsx2 } from "react/jsx-runtime";
function Label({ children, kicker = false, onDark = false, className = "" }) {
  const cls = ["label", kicker ? "u-kick" : "", onDark ? "label--cream" : "", className].filter(Boolean).join(" ");
  return /* @__PURE__ */ jsx2("span", { className: cls, children });
}

// src/components/Spark.tsx
import { jsx as jsx3, jsxs as jsxs2 } from "react/jsx-runtime";
function Spark({ large = false, className = "" }) {
  const cls = ["spark", large ? "spark-lg" : "", className].filter(Boolean).join(" ");
  return /* @__PURE__ */ jsxs2("span", { className: cls, "aria-hidden": "true", children: [
    /* @__PURE__ */ jsx3("i", {}),
    /* @__PURE__ */ jsx3("i", {}),
    /* @__PURE__ */ jsx3("i", {})
  ] });
}

// src/components/Emblem.tsx
import { jsx as jsx4 } from "react/jsx-runtime";
function Emblem({ size = 96, watermark = false, className = "" }) {
  return /* @__PURE__ */ jsx4(
    "span",
    {
      className: ["emblem", className].filter(Boolean).join(" "),
      "aria-hidden": "true",
      style: { width: size, height: size, display: "block", opacity: watermark ? 0.07 : 0.92 }
    }
  );
}

// src/components/Typography.tsx
import { jsx as jsx5, jsxs as jsxs3 } from "react/jsx-runtime";
function Display({ children, as: Tag = "h1", className = "" }) {
  return /* @__PURE__ */ jsx5(Tag, { className: ["display", className].filter(Boolean).join(" "), children });
}
function Heading({ children, level = 2, as, className = "" }) {
  const Tag = as ?? (level === 2 ? "h2" : "h3");
  return /* @__PURE__ */ jsx5(Tag, { className: [`h${level}`, className].filter(Boolean).join(" "), children });
}
function Text({ children, variant = "body", className = "" }) {
  const cls = [variant === "body" ? "" : variant, className].filter(Boolean).join(" ");
  return /* @__PURE__ */ jsx5("p", { className: cls || void 0, children });
}
function Em({ children, className = "" }) {
  return /* @__PURE__ */ jsx5("span", { className: ["em", className].filter(Boolean).join(" "), children });
}
function Signature({ children, role, className = "" }) {
  return /* @__PURE__ */ jsxs3("div", { className: className || void 0, children: [
    /* @__PURE__ */ jsx5("div", { className: "sig", children }),
    role ? /* @__PURE__ */ jsx5("span", { children: role }) : null
  ] });
}

// src/components/Section.tsx
import { jsx as jsx6, jsxs as jsxs4 } from "react/jsx-runtime";
function Section({
  children,
  tone = "paper",
  padding = "md",
  id,
  className = ""
}) {
  const toneClass = tone === "dark" ? "problem" : tone === "cream" ? "cta" : "";
  const cls = [toneClass, padding === "sm" ? "sec-pad-sm" : "sec-pad", className].filter(Boolean).join(" ");
  return /* @__PURE__ */ jsx6("section", { className: cls, id, children: /* @__PURE__ */ jsx6("div", { className: "wrap", children }) });
}
function SectionHead({
  label,
  title,
  sub,
  center = false,
  onDark = false,
  className = ""
}) {
  const cls = ["sec-head", center ? "center" : "", className].filter(Boolean).join(" ");
  return /* @__PURE__ */ jsxs4("div", { className: cls, children: [
    label ? /* @__PURE__ */ jsx6("span", { className: ["label", "u-kick", onDark ? "label--cream" : ""].filter(Boolean).join(" "), children: label }) : null,
    /* @__PURE__ */ jsx6("h2", { className: "h2", children: title }),
    sub ? /* @__PURE__ */ jsx6("p", { className: "lead", children: sub }) : null
  ] });
}

// src/components/PackageCard.tsx
import { jsx as jsx7, jsxs as jsxs5 } from "react/jsx-runtime";
var Check = () => /* @__PURE__ */ jsx7("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, "aria-hidden": "true", children: /* @__PURE__ */ jsx7("path", { d: "M5 12l5 5L20 6" }) });
function PackageCard({
  tag,
  name,
  priceLabel,
  price,
  description,
  featuresLabel,
  features = [],
  ctaLabel,
  ctaHref,
  onCta,
  featured = false,
  mid = false,
  className = ""
}) {
  const cls = ["pkg", featured ? "feat" : "", mid && !featured ? "pkg-mid" : "", className].filter(Boolean).join(" ");
  return /* @__PURE__ */ jsxs5("article", { className: cls, children: [
    tag ? /* @__PURE__ */ jsx7("span", { className: "pk-tag", children: tag }) : null,
    /* @__PURE__ */ jsx7("h3", { children: name }),
    /* @__PURE__ */ jsxs5("div", { className: "pk-price", children: [
      priceLabel ? /* @__PURE__ */ jsx7("span", { className: "from", children: priceLabel }) : null,
      price
    ] }),
    /* @__PURE__ */ jsx7("p", { className: "pk-desc", children: description }),
    featuresLabel ? /* @__PURE__ */ jsx7("p", { className: "pk-incl", children: featuresLabel }) : null,
    features.length ? /* @__PURE__ */ jsx7("ul", { children: features.map((f, i) => /* @__PURE__ */ jsxs5("li", { children: [
      /* @__PURE__ */ jsx7(Check, {}),
      /* @__PURE__ */ jsx7("span", { children: f.text })
    ] }, i)) }) : null,
    ctaHref ? /* @__PURE__ */ jsx7("a", { className: `btn ${featured ? "btn-clay" : "btn-ghost"}`, href: ctaHref, children: ctaLabel }) : /* @__PURE__ */ jsx7("button", { type: "button", className: `btn ${featured ? "btn-clay" : "btn-ghost"}`, onClick: onCta, children: ctaLabel })
  ] });
}
function PackageGrid({ children, className = "" }) {
  return /* @__PURE__ */ jsx7("div", { className: ["pkgs", className].filter(Boolean).join(" "), children });
}

// src/components/Testimonial.tsx
import { jsx as jsx8, jsxs as jsxs6 } from "react/jsx-runtime";
var Star = () => /* @__PURE__ */ jsx8("svg", { viewBox: "0 0 24 24", fill: "currentColor", "aria-hidden": "true", children: /* @__PURE__ */ jsx8("path", { d: "M12 2l2.4 7.4H22l-6 4.5 2.3 7.1L12 16.6 5.7 21l2.3-7.1-6-4.5h7.6z" }) });
function Testimonial({ quote, name, role, rating, className = "" }) {
  return /* @__PURE__ */ jsxs6("figure", { className: ["tcard", className].filter(Boolean).join(" "), children: [
    typeof rating === "number" ? /* @__PURE__ */ jsx8("div", { className: "stars", "aria-label": `${rating} out of 5`, children: Array.from({ length: rating }, (_, i) => /* @__PURE__ */ jsx8(Star, {}, i)) }) : null,
    /* @__PURE__ */ jsx8("blockquote", { children: quote }),
    /* @__PURE__ */ jsxs6("figcaption", { className: "tperson", children: [
      /* @__PURE__ */ jsx8("span", { className: "av", children: name.charAt(0) }),
      /* @__PURE__ */ jsxs6("span", { children: [
        /* @__PURE__ */ jsx8("span", { className: "tn", children: name }),
        role ? /* @__PURE__ */ jsx8("span", { className: "tr", children: role }) : null
      ] })
    ] })
  ] });
}

// src/components/CredentialChips.tsx
import { jsx as jsx9 } from "react/jsx-runtime";
function CredentialChip({ children, className = "" }) {
  return /* @__PURE__ */ jsx9("span", { className: ["cred", className].filter(Boolean).join(" "), children });
}
function CredentialRibbon({ children, className = "" }) {
  return /* @__PURE__ */ jsx9("div", { className: ["creds", className].filter(Boolean).join(" "), children: /* @__PURE__ */ jsx9("div", { className: "wrap", children: /* @__PURE__ */ jsx9("div", { className: "creds-in", children }) }) });
}

// src/components/CtaCard.tsx
import { jsx as jsx10, jsxs as jsxs7 } from "react/jsx-runtime";
function CtaCard({ label, title, body, aside, className = "" }) {
  return /* @__PURE__ */ jsx10("section", { className: ["cta", "sec-pad", className].filter(Boolean).join(" "), children: /* @__PURE__ */ jsx10("div", { className: "wrap", children: /* @__PURE__ */ jsxs7("div", { className: "cta-card", children: [
    /* @__PURE__ */ jsx10("span", { className: "emblem cta-wm", "aria-hidden": "true" }),
    /* @__PURE__ */ jsxs7("div", { className: "cta-grid", children: [
      /* @__PURE__ */ jsxs7("div", { children: [
        label ? /* @__PURE__ */ jsx10("span", { className: "label", children: label }) : null,
        /* @__PURE__ */ jsx10("h3", { className: "h2", children: title }),
        body ? /* @__PURE__ */ jsx10("p", { children: body }) : null
      ] }),
      aside ? /* @__PURE__ */ jsx10("div", { children: aside }) : null
    ] })
  ] }) }) });
}

// src/components/PhotoFrame.tsx
import { jsx as jsx11 } from "react/jsx-runtime";
function PhotoFrame({
  src,
  alt,
  width,
  height,
  objectPosition = "center 22%",
  className = ""
}) {
  return /* @__PURE__ */ jsx11("figure", { className: ["about-photo", className].filter(Boolean).join(" "), style: { margin: 0 }, children: /* @__PURE__ */ jsx11("img", { src, alt, width, height, loading: "lazy", decoding: "async", style: { objectPosition } }) });
}

// src/components/Faq.tsx
import { useLayoutEffect, useRef, useState } from "react";
import { jsx as jsx12, jsxs as jsxs8 } from "react/jsx-runtime";
function FaqItem({ question, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const panel = useRef(null);
  useLayoutEffect(() => {
    const el = panel.current;
    if (el) el.style.maxHeight = open ? `${el.scrollHeight}px` : "0px";
  }, [open, children]);
  return /* @__PURE__ */ jsxs8("div", { className: ["faq-item", open ? "open" : ""].filter(Boolean).join(" "), children: [
    /* @__PURE__ */ jsxs8("button", { className: "faq-q", "aria-expanded": open, onClick: () => setOpen(!open), children: [
      /* @__PURE__ */ jsx12("span", { children: question }),
      /* @__PURE__ */ jsx12("span", { className: "fq-ic", "aria-hidden": "true" })
    ] }),
    /* @__PURE__ */ jsx12("div", { className: "faq-a", ref: panel, children: /* @__PURE__ */ jsx12("div", { className: "faq-a-in", children }) })
  ] });
}
function FaqList({ children, className = "" }) {
  return /* @__PURE__ */ jsx12("div", { className: ["faq-list", className].filter(Boolean).join(" "), children });
}

// src/components/MetaList.tsx
import { jsx as jsx13, jsxs as jsxs9 } from "react/jsx-runtime";
function MetaList({ entries, className = "" }) {
  return /* @__PURE__ */ jsx13("dl", { className: ["about-meta", className].filter(Boolean).join(" "), children: entries.map((e, i) => /* @__PURE__ */ jsxs9("div", { children: [
    /* @__PURE__ */ jsx13("dt", { children: e.term }),
    /* @__PURE__ */ jsx13("dd", { children: e.value })
  ] }, i)) });
}

// src/components/ImageBand.tsx
import { jsx as jsx14, jsxs as jsxs10 } from "react/jsx-runtime";
function ImageBand({ src, alt, caption, label, hero = false, className = "" }) {
  const cls = ["img-band", hero ? "img-band--hero" : "", className].filter(Boolean).join(" ");
  return /* @__PURE__ */ jsxs10("div", { className: cls, children: [
    /* @__PURE__ */ jsx14("img", { src, alt, loading: "lazy", decoding: "async" }),
    caption || label ? /* @__PURE__ */ jsxs10("div", { className: "img-cap", children: [
      label ? /* @__PURE__ */ jsx14("span", { className: "label", children: label }) : null,
      caption ? /* @__PURE__ */ jsx14("p", { children: caption }) : null
    ] }) : null
  ] });
}
export {
  Button,
  CredentialChip,
  CredentialRibbon,
  CtaCard,
  Display,
  Em,
  Emblem,
  FaqItem,
  FaqList,
  Heading,
  ImageBand,
  Label,
  MetaList,
  PackageCard,
  PackageGrid,
  PhotoFrame,
  Section,
  SectionHead,
  Signature,
  Spark,
  Testimonial,
  Text
};
