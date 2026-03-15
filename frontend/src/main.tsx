/**
 * Application entry point
 */

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { msalInstance } from "@/auth/msal";
import "./styles.css";

const rootElement = document.getElementById("root");

async function bootstrap() {
  await msalInstance.initialize();

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
