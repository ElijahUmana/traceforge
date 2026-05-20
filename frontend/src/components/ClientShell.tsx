"use client";

import { useState, useEffect } from "react";
import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { NavBar } from "./NavBar";

export function ClientShell({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  return (
    <ChakraProvider value={defaultSystem}>
      <NavBar />
      <main style={{ padding: "24px", maxWidth: "1400px", margin: "0 auto" }}>
        {children}
      </main>
    </ChakraProvider>
  );
}
