import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import { ErrorBoundary } from "./ErrorBoundary.jsx";
import "./styles.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  document.body.innerHTML = "<p>Unable to start app: root element was not found.</p>";
} else {
  createRoot(rootElement).render(
    <React.StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </React.StrictMode>,
  );
}
