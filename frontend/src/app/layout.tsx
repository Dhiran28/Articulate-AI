import type { Metadata } from "next";
import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
