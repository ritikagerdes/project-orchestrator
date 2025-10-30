import React, { useEffect, useState } from "react";
import api from '../../services/axiosConfig';


export default function EmbeddingsAdmin() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await api.get("/api/admin/embeddings");
      setItems(res.data.items || []);
    } catch (err) {
      console.error(err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function triggerReindex() {
    setReindexing(true);
    try {
      await api.post("/api/admin/reindex", { background: true });
      // poll for a short while then refresh
      setTimeout(() => load(), 1500);
    } catch (err) {
      console.error(err);
    } finally {
      setReindexing(false);
    }
  }

  return (
    <div style={{ padding: 20 }}>
      <h3>Embeddings / Index Admin</h3>
      <div style={{ marginBottom: 12 }}>
        <button onClick={triggerReindex} disabled={reindexing}>{reindexing ? "Reindexing..." : "Reindex Now"}</button>
        <button onClick={load} style={{ marginLeft: 8 }}>Refresh</button>
      </div>
      {loading ? <div>Loading…</div> : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th>ID</th><th>Filename</th><th>Price</th><th>Has Vector</th></tr></thead>
          <tbody>
            {items.map(it => (
              <tr key={it.id}>
                <td style={{ border: "1px solid #eee", padding: 6 }}>{it.id}</td>
                <td style={{ border: "1px solid #eee", padding: 6 }}>{it.filename}</td>
                <td style={{ border: "1px solid #eee", padding: 6 }}>{it.final_price}</td>
                <td style={{ border: "1px solid #eee", padding: 6 }}>{it.has_vector ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}