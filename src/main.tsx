import {StrictMode} from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter, Navigate, Route, Routes} from "react-router-dom";

import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/news" replace />} />
        <Route path="/news" element={<App />} />
        <Route path="/analysis" element={<App />} />
        <Route path="*" element={<Navigate to="/news" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
