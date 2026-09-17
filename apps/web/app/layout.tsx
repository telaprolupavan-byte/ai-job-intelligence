import type { Metadata } from "next";
import { Inter, Syne, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

// Geometric display face used sparingly for hero/page headings — the
// "futuristic but restrained" half of the Cyber-Spidey type system.
const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});

// Technical/data typeface for metadata, labels, and evidence text —
// replaces Space Mono with a more legible mono at small sizes.
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "AI Job Intelligence",
  description:
    "AI-powered job discovery, matching, ATS analysis, and resume intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${syne.variable} ${jetbrainsMono.variable}`}
      >
        {children}
      </body>
    </html>
  );
}