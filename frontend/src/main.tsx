/**
 * Application entry point
 */

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initializeMsalSession, msalInstance } from "@/auth/msal";
import "./styles.css";

const rootElement = document.getElementById("root");

async function bootstrap() {
  await msalInstance.initialize();
  await initializeMsalSession(window.location.pathname);

  if (rootElement && !rootElement.innerHTML) {
    const root = ReactDOM.createRoot(rootElement);
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  }
}

void bootstrap();
