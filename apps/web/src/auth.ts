import { cache } from "react";
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
  pages: { signIn: "/signin" },
  callbacks: {
    session({ session, token }) {
      if (session.user && token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
  },
});

// Request-deduped session read. A single render can resolve auth in more than one
// place (the layout's redirect gate AND, deeper, bffFetch minting a service JWT); a
// second bare `auth()` call in that nested scope can lose the request/cookie context
// and come back null. Wrapping in React `cache` means every caller in one request
// shares the first successful result. Use this everywhere instead of `auth` directly.
export const getSession = cache(auth);
