import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ExceptionLoop",
  description: "Operational control plane for AI agent exceptions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
