"use client";

import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { useState, useEffect } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <>{children}</>;
  }

  return <ChakraProvider value={defaultSystem}>{children}</ChakraProvider>;
}
