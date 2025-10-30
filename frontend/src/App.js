import React from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import Home from "./components/Home";
import AdminPage from "./components/AdminPage";
import ChatButton from "./components/ChatButton";
import EmbeddingsAdmin from "./components/Admin/EmbeddingsAdmin"; // added admin UI import

function App() {
  return (
    <Router>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 12, borderBottom: "1px solid #eee", background: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link to="/" style={{ textDecoration: "none", color: "#111827", fontWeight: 600 }}>Home</Link>
          <Link to="/projects" style={{ textDecoration: "none", color: "#6b7280" }}>Projects</Link>
        </div>
        <nav>
          <Link to="/admin" style={{ textDecoration: "none", color: "#1d4ed8", fontWeight: 500, padding: "10px" }}>Admin</Link>
          <Link to="/admin/embeddings" style={{ textDecoration: "none", color: "#1d4ed8", fontWeight: 500, padding: "10px" }}>Embeddings</Link>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/embeddings" element={<EmbeddingsAdmin />} /> {/* admin route */}
      </Routes>
import EnvDebug from './components/EnvDebug';

        {/* Chat button rendered site-wide. AdminPage will render its own preview but this is the production chat. */}
      <ChatButton />
    
    </Router>
  );
}

export default App;