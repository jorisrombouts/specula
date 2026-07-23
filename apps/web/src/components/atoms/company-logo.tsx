"use client";

import { useState } from "react";

// Two-letter fallback from a company name (first letters of the first two words,
// else the first two characters) — shown when there's no favicon or it fails to load.
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.trim().slice(0, 2).toUpperCase() || "—";
}

// A company mark. Live data stores `logo` as a favicon URL (per the "logos via favicon
// URL" design); seed/demo data uses short initials. Render a URL as an <img> (with an
// initials fallback for the many favicons that 404 — e.g. fabricated ATS-host domains),
// and a non-URL as text. `className` carries the caller's box styling (size/shape/bg).
export function CompanyLogo({
  src,
  name,
  className,
}: {
  src: string;
  name: string;
  className: string;
}) {
  const [broken, setBroken] = useState(false);
  const isUrl = /^https?:\/\//i.test(src);

  return (
    <span className={`overflow-hidden ${className}`}>
      {isUrl && !broken ? (
        <img
          src={src}
          alt=""
          className="max-h-full max-w-full object-contain"
          onError={() => setBroken(true)}
        />
      ) : (
        <span>{isUrl ? initials(name) : src}</span>
      )}
    </span>
  );
}
