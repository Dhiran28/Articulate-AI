import type { Metadata } from "next";
import "./globals.css";

import { Header } from "@/components/Header";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Articulate AI",
  description: "An AI-powered communication coach for structural thinking.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <Header />
          {children}
        </Providers>
      </body>
    </html>
  );
}
