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
    return <p><span className="status-label">Backend</span><span className="status-badge status-badge--pending">Checking</span></p>;
  }

  if (connectionState === "failed") {
    return <p role="alert"><span className="status-label">Backend</span><span className="status-badge status-badge--error">Unavailable</span></p>;
  }

  return <p><span className="status-label">Backend</span><span className="status-badge status-badge--success">Connected</span></p>;
}

export default BackendStatus;
