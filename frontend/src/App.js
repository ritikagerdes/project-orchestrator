import React from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import Home from "./components/Home";
import AdminPage from "./components/AdminPage";
import ChatButton from "./components/ChatButton";

export default function App() {
  return (
    <Router>
      <div style={{ padding: 12, borderBottom: "1px solid #eee", display: "flex", justifyContent: "space-between" }}>
        <div><Link to="/">Proposal Orchestrator</Link></div>
        <div style={{ gap: 12 }}>
          <Link to="/admin">Admin</Link>
        </div>
      </div>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>

      {/* Chat button rendered site-wide. AdminPage will render its own preview but this is the production chat. */}
      <ChatButton />
    </Router>
  );
}