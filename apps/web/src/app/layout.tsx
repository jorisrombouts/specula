import type { Metadata } from "next";
import {
  Spectral,
  Hanken_Grotesk,
  Geist_Mono,
  Newsreader,
  Source_Serif_4,
} from "next/font/google";
import "./globals.css";
import { INIT_SCRIPT } from "@/lib/tweaks-init";

// Spectral is NOT a variable font on Google Fonts — explicit weights are required.
const spectral = Spectral({
  variable: "--font-spectral",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
// Hanken Grotesk, Geist Mono, Newsreader, Source Serif 4 are variable fonts — omit weight.
const hanken = Hanken_Grotesk({
  variable: "--font-hanken",
  subsets: ["latin"],
});
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});
// Loaded for the M1 font Tweak; not applied to anything in M0a.
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
});
const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Specula",
  description: "Specula — role ledger",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${spectral.variable} ${hanken.variable} ${geistMono.variable} ${newsreader.variable} ${sourceSerif.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: INIT_SCRIPT }} />
      </head>
      <body className="bg-paper text-ink">{children}</body>
    </html>
  );
}
