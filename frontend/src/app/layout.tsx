import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "TraceForge - Cross-Agent Decision Provenance",
  description:
    "Production-grade cross-agent decision provenance on Neo4j + AWS Strands + Bedrock AgentCore",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers>
          <NavBar />
          <main style={{ padding: "24px", maxWidth: "1400px", margin: "0 auto" }}>
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
