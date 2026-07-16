import { useEffect, useState } from "react";

import { getBackendHealth } from "../api/health";

type ConnectionState = "checking" | "connected" | "failed";

function BackendStatus() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");

  useEffect(() => {
    async function checkBackend(): Promise<void> {
      try {
        const response = await getBackendHealth();

        setConnectionState(
          response.status === "healthy" ? "connected" : "failed",
        );
      } catch {
        setConnectionState("failed");
      }
    }

    void checkBackend();
  }, []);

  if (connectionState === "checking") {
    return <p>Checking backend connection...</p>;
  }

  if (connectionState === "failed") {
    return <p role="alert">Backend connection failed.</p>;
  }

  return <p>Backend connected successfully.</p>;
}

export default BackendStatus;
