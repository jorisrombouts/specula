"use client";

// Emits an inline pre-paint script that runs during HTML parsing on hard loads
// (server render → type="text/javascript", so it executes) but is inert on the
// client (client render → type="text/plain", which React treats as a non-executable
// data block and therefore does NOT warn about — see isScriptDataBlock in react-dom).
// suppressHydrationWarning covers the deliberate server/client type mismatch.
//
// "use client" is load-bearing: it makes this render function run on the client at
// all, so the ternary can evaluate to "text/plain" there. Without it the component
// renders only on the server and the client always sees "text/javascript", which
// still triggers React's "Encountered a script tag while rendering" warning.
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
