import React from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import "@google/model-viewer";
import App from "./App";
import { useStore, connectWs } from "./store";

document.documentElement.classList.toggle("dark", useStore.getState().theme === "dark");
connectWs();
createRoot(document.getElementById("root")).render(<App />);
