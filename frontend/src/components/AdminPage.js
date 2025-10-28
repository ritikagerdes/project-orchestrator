import React, { useEffect, useState } from "react";
import axios from "axios";
import ChatButton from "./ChatButton";

const CANONICAL_ROLES = {
  "Software Developer": 80.0,
  "Senior Software Developer": 120.0,
  "Software Architect": 150.0,
  "WordPress Developer": 70.0,
  "Project Manager": 95.0,
  "Cloud Architect / DevOps Engineer": 140.0
};

export default function AdminPage() {
  const [rates, setRates] = useState({});
  const [editing, setEditing] = useState({});
  const [settings, setSettings] = useState({ chat_enabled: true, chat_position: "bottom-right" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchRates();
    fetchSettings();
  }, []);

  async function fetchRates() {
    try {
      const res = await axios.get("/api/admin/ratecard");
      const fetched = (res.data && res.data.rates) ? res.data.rates : {};
      // if API returned nothing, seed with canonical roles
      const seed = Object.keys(fetched).length ? fetched : CANONICAL_ROLES;
      setRates(seed);
      setEditing(seed);
    } catch (err) {
      // fallback to canonical roles when API fails
      setRates(CANONICAL_ROLES);
      setEditing(CANONICAL_ROLES);
      console.error("fetchRates", err);
    }
  }

  async function fetchSettings() {
    try {
      const res = await axios.get("/api/admin/settings");
      setSettings(res.data || settings);
    } catch (err) {
      // keep defaults if settings not available
      console.error("fetchSettings", err);
    }
  }

  function onRateChange(role, value) {
    setEditing(prev => ({ ...prev, [role]: value }));
  }

  function addRole() {
    const name = `New Role ${Object.keys(editing).length + 1}`;
    setEditing(prev => ({ ...prev, [name]: 50 }));
  }

  function removeRole(role) {
    const next = { ...editing };
    delete next[role];
    setEditing(next);
  }

  async function saveRateCard() {
    setSaving(true);
    try {
      await axios.put("/api/admin/ratecard", { rates: editing });
      setRates(editing);
      alert("Rate card saved.");
    } catch (err) {
      console.error("saveRateCard", err);
      alert("Failed to save rate card. See console.");
    } finally {
      setSaving(false);
    }
  }

  async function saveSettings() {
    try {
      await axios.put("/api/admin/settings", settings);
      alert("Settings saved.");
    } catch (err) {
      console.error("saveSettings", err);
      alert("Failed to save settings.");
    }
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Admin — Rate Card</h2>
      <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 320 }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>Role</th>
                <th style={{ textAlign: "left" }}>Rate ($/hr)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(editing).map(role => (
                <tr key={role}>
                  <td style={{ padding: "8px 4px" }}>{role}</td>
                  <td style={{ padding: "8px 4px" }}>
                    <input
                      type="number"
                      value={editing[role]}
                      onChange={(e) => onRateChange(role, Number(e.target.value))}
                      style={{ width: 120 }}
                    />
                  </td>
                  <td style={{ padding: "8px 4px" }}>
                    <button onClick={() => removeRole(role)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 12 }}>
            <button onClick={addRole}>Add Role</button>
            <button onClick={saveRateCard} disabled={saving} style={{ marginLeft: 8 }}>
              {saving ? "Saving..." : "Save rate card"}
            </button>
          </div>
        </div>

        <div style={{ width: 320, border: "1px solid #e2e8f0", padding: 12, borderRadius: 6 }}>
          <h3>UI Settings</h3>
          <label style={{ display: "block", marginBottom: 8 }}>
            <input
              type="checkbox"
              checked={settings.chat_enabled}
              onChange={(e) => setSettings(s => ({ ...s, chat_enabled: e.target.checked }))}
            />{" "}
            Enable chat button
          </label>

          <label style={{ display: "block", marginBottom: 8 }}>
            Chat position:
            <select
              value={settings.chat_position}
              onChange={(e) => setSettings(s => ({ ...s, chat_position: e.target.value }))}
              style={{ marginLeft: 8 }}
            >
              <option value="bottom-right">Bottom right</option>
              <option value="bottom-left">Bottom left</option>
            </select>
          </label>

          <div style={{ marginTop: 12 }}>
            <button onClick={saveSettings}>Save settings</button>
          </div>

          <div style={{ marginTop: 18 }}>
            <strong>Preview</strong>
            <div style={{ position: "relative", height: 140 }}>
              {/* preview uses stage mode and always visible in preview */}
              <ChatButton visible={true} position={settings.chat_position} showLabel={true} mode="stage" />
            </div>
            <small>Chat button preview — real button will appear site-wide if enabled.</small>
          </div>
        </div>
      </div>

      {/* Chat button visible on admin page as requested; preview uses stage mode */}
      <ChatButton visible={settings.chat_enabled} position={settings.chat_position} mode="stage" />
    </div>
  );
}