import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

export default function ChatWindow({ onClose, position = "bottom-right", mode = "production" }) {
  const [messages, setMessages] = useState([
    { from: "bot", text: "Hi — describe your project and I'll help estimate it." }
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingQuestions, setPendingQuestions] = useState([]); // questions queue
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [answers, setAnswers] = useState([]); // collected answers in order
  const [lastUserQuery, setLastUserQuery] = useState(""); // original user text for follow-up
  const [completed, setCompleted] = useState(false); // whether flow finished with an estimate
  const [contact, setContact] = useState({ name: "", email: "", phone: "" });
  const [quoteCreated, setQuoteCreated] = useState(false);
  const [latestSowB64, setLatestSowB64] = useState(null);
  const saveTimerRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, pendingQuestions, currentQIndex]);

  // Auto-save chat when messages change (debounced).
  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      try {
        await axios.post("/api/chat/save", { title: `chat-${Date.now()}.json`, messages });
      } catch (err) {
        // silent
        // eslint-disable-next-line no-console
        console.error("autosave failed", err);
      }
    }, 1000);
    return () => clearTimeout(saveTimerRef.current);
  }, [messages]);

  const pushMessage = (m) => setMessages((prev) => [...prev, m]);

  // helper: detect if contact question already answered (in contact state or answers list)
  function _alreadyAnsweredContact(field) {
    const key = field.toLowerCase();
    if (key === "name" && contact.name) return true;
    if (key === "email" && contact.email) return true;
    for (let a of answers) {
      const q = (a.question || "").toLowerCase();
      if (q.includes(key) && a.answer) return true;
    }
    return false;
  }

  async function sendInitial(text) {
    setSending(true);
    try {
      const res = await axios.post("/api/message", { text, client_info: {}, mode });
      const data = res.data;

      const contactQs = [];
      if (!_alreadyAnsweredContact("name")) contactQs.push("What's your name?");
      if (!_alreadyAnsweredContact("email")) contactQs.push("What's your email?");
      const serverQs = Array.isArray(data.questions) ? data.questions : [];
      // remove any serverQs that are duplicates of contactQs
      const serverQsFiltered = serverQs.filter((q) => {
        const ql = (q || "").toLowerCase();
        if (ql.includes("name") && _alreadyAnsweredContact("name")) return false;
        if (ql.includes("email") && _alreadyAnsweredContact("email")) return false;
        return true;
      });
      const allQs = [...contactQs, ...serverQsFiltered];

      if (allQs.length > 0) {
        setPendingQuestions(allQs);
        setCurrentQIndex(0);
        setAnswers([]);
        pushMessage({ from: "bot", text: allQs[0] });
      } else {
        if (contactQs.length > 0) {
          setPendingQuestions(contactQs);
          setCurrentQIndex(0);
          setAnswers([]);
          pushMessage({ from: "bot", text: contactQs[0] });
        } else if (data.status === "completed") {
          await handleCompletedResponse(data);
        } else if (data.summary) {
          pushMessage({ from: "bot", text: data.summary });
        }
      }
    } catch (err) {
      pushMessage({ from: "bot", text: "Error contacting server." });
    } finally {
      setSending(false);
    }
  }

  async function sendFollowUp() {
    setSending(true);
    try {
      const followPayload = { text: lastUserQuery, client_info: { answers }, mode };
      const res = await axios.post("/api/message", followPayload);
      const data = res.data;

      setPendingQuestions([]);
      setCurrentQIndex(0);
      setAnswers([]);

      if (data.status === "completed") {
        await handleCompletedResponse(data);
      } else if (Array.isArray(data.questions) && data.questions.length > 0) {
        const contactQs = [];
        if (!contact.name) contactQs.push("What's your name?");
        if (!contact.email) contactQs.push("What's your email?");
        const allQs = [...contactQs, ...data.questions];
        setPendingQuestions(allQs);
        setCurrentQIndex(0);
        pushMessage({ from: "bot", text: allQs[0] });
      } else {
        pushMessage({ from: "bot", text: JSON.stringify(data) });
      }
    } catch (err) {
      pushMessage({ from: "bot", text: "Error contacting server on follow-up." });
    } finally {
      setSending(false);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text) return;

    if (pendingQuestions.length > 0) {
      pushMessage({ from: "user", text });
      setAnswers((prev) => [...prev, { question: pendingQuestions[currentQIndex], answer: text }]);

      const qText = (pendingQuestions[currentQIndex] || "").toLowerCase();
      if (qText.includes("name") && !contact.name) setContact((c) => ({ ...c, name: text }));
      if (qText.includes("email") && !contact.email) setContact((c) => ({ ...c, email: text }));
      if (qText.includes("phone") && !contact.phone) setContact((c) => ({ ...c, phone: text }));

      setInput("");

      if (currentQIndex + 1 < pendingQuestions.length) {
        const nextIndex = currentQIndex + 1;
        setCurrentQIndex(nextIndex);
        pushMessage({ from: "bot", text: pendingQuestions[nextIndex] });
      } else {
        await sendFollowUp();
      }
      return;
    }

    pushMessage({ from: "user", text });
    setInput("");
    setLastUserQuery(text);
    await sendInitial(text);
  }

  function _extract_sow_b64_from_last_bot() {
    const sow_text = messages.filter((m) => m.from === "bot").map((m) => m.text).join("\n\n");
    try {
      return btoa(unescape(encodeURIComponent(sow_text)));
    } catch (e) {
      return btoa(sow_text);
    }
  }

  // in handleCompletedResponse, only ask missing contact questions once
  async function handleCompletedResponse(data) {
    try {
      // if name/email missing, request them (but don't duplicate if already asked)
      const missing = [];
      if (!_alreadyAnsweredContact("name")) missing.push("What's your name?");
      if (!_alreadyAnsweredContact("email")) missing.push("What's your email?");
      if (missing.length > 0) {
        setPendingQuestions(missing);
        setCurrentQIndex(0);
        pushMessage({ from: "bot", text: missing[0] });
        // save the completed payload to finalize once contact provided
        window.__pending_completed_payload = data;
        return;
      }

      // create PDF
      pushMessage({ from: "bot", text: "Creating your estimate PDF..." });

      const title = `ProjectQuote-${Date.now()}`;
      const payload = { sow_b64: data.sow, estimate: data.estimate, title };
      const res = await axios.post("/api/sow/create", payload);
      const download_url = res?.data?.download_url;

      // short message with link only (no sow or estimate text)
      pushMessage({ from: "bot", text: "Estimate created. Download or share:", url: download_url });

      setLatestSowB64(data.sow || null);
      setQuoteCreated(true);
      setCompleted(true);

      if (contact.name && contact.email) {
        await sendLead({ completed: true, sow_b64: data.sow });
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("create pdf", err);
      pushMessage({ from: "bot", text: "Failed to create estimate PDF. Try again later." });
    }
  }

  // when contact becomes available, finalize any pending completed payload
  useEffect(() => {
    if ((contact.name && contact.email) && window.__pending_completed_payload) {
      const pending = window.__pending_completed_payload;
      window.__pending_completed_payload = null;
      handleCompletedResponse(pending);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contact.name, contact.email]);

  async function sendLead({ completed = false, sow_b64 = null } = {}) {
    if (!contact.name || !contact.email) return;
    try {
      const payload = {
        name: contact.name,
        email: contact.email,
        message: completed ? "Project quote completed via estimator" : "Chat interrupted / incomplete - request follow up",
        sow_b64,
        chat: messages
      };
      await axios.post("/api/hubspot/send", payload);
      pushMessage({ from: "bot", text: "Thanks — your lead was sent to our sales team." });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("sendLead", err);
      pushMessage({ from: "bot", text: "Unable to send contact to sales automatically." });
    }
  }

  async function handleClose() {
    if (!contact.name || !contact.email) {
      const ok = window.confirm("You haven't provided name and email. Sales team needs contact info to follow up. Close anyway?");
      if (!ok) return;
    }
    if (!completed && (contact.name || contact.email || contact.phone)) {
      await sendLead({ completed: false, sow_b64: _extract_sow_b64_from_last_bot() });
    }
    onClose && onClose();
  }

  async function handleShareCurrentLink() {
    // create zip with chat text and PDF (if available) on server and download it
    try {
      const title = `share-${Date.now()}`;
      const payload = {
        title,
        messages,
        sow_b64: latestSowB64,
        estimate: null
      };
      const resp = await axios.post("/api/share/zip", payload, { responseType: "blob" });
      const blob = new Blob([resp.data], { type: "application/zip" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      pushMessage({ from: "bot", text: "Packaged chat + quote and started download." });
    } catch (err) {
      console.error("share zip failed", err);
      pushMessage({ from: "bot", text: "Failed to create package for sharing." });
    }
  }

  return (
    <div
      className={`chat-window ${position === "bottom-left" ? "chat-btn-left" : "chat-btn-right"}`}
      style={{
        width: 420,
        boxShadow: "0 6px 18px rgba(15,23,42,0.12)",
        borderRadius: 10,
        overflow: "hidden",
        fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial"
      }}
    >
      <div style={{ padding: 12, borderBottom: "1px solid #eee", background: "#fff", display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <strong style={{ fontSize: 14 }}>Project Quote & Estimator ({mode})</strong>
          <div style={{ fontSize: 12, color: "#6b7280" }}>Describe your project and I'll help estimate it.</div>
        </div>
        <button
          onClick={handleClose}
          style={{
            background: "transparent",
            color: "#374151",
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            cursor: "pointer"
          }}
        >
          Close
        </button>
      </div>

      <div ref={listRef} style={{ padding: 12, height: 340, overflowY: "auto", background: "#f8fbff" }}>
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 10, display: "flex", justifyContent: m.from === "user" ? "flex-end" : "flex-start" }}>
            <div
              style={{
                maxWidth: "78%",
                display: "inline-block",
                padding: "10px 12px",
                borderRadius: 12,
                background: m.from === "user" ? "#eef2ff" : "#ffffff",
                boxShadow: m.from === "user" ? "none" : "0 1px 2px rgba(0,0,0,0.03)",
                color: "#111827",
                fontSize: 13,
                lineHeight: "18px"
              }}
            >
              <div>{m.text}</div>
              {m.url && (
                <div style={{ marginTop: 8 }}>
                  <a href={m.url} target="_blank" rel="noreferrer" style={{ color: "#1d4ed8" }}>
                    Download estimate PDF
                  </a>
                  <button
                    style={{ marginLeft: 8, padding: "6px 8px", borderRadius: 6, border: "1px solid #e5e7eb", background: "transparent", cursor: "pointer" }}
                    onClick={() => {
                      if (m.url) {
                        navigator.clipboard.writeText(m.url);
                        pushMessage({ from: "bot", text: "Link copied." });
                      }
                    }}
                  >
                    Copy link
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div style={{ padding: 12, borderTop: "1px solid #eee", background: "#fff", display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={pendingQuestions.length > 0 ? "Answer the question..." : "Describe your project..."}
          style={{ flex: 1, padding: "10px 12px", borderRadius: 8, border: "1px solid #e6eef8" }}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
        />
        <button
          onClick={handleSend}
          disabled={sending}
          style={{
            background: sending ? "#94a3b8" : "#1d4ed8",
            color: "#fff",
            padding: "8px 14px",
            borderRadius: 10,
            border: "none",
            boxShadow: "0 2px 6px rgba(0,0,0,0.08)",
            cursor: sending ? "not-allowed" : "pointer"
          }}
        >
          {sending ? "Sending..." : "Send"}
        </button>
      </div>

      <div style={{ padding: 10, borderTop: "1px solid #f1f5f9", background: "#fff", display: "flex", justifyContent: "space-between", gap: 8 }}>
        <div style={{ color: "#6b7280", fontSize: 12, alignSelf: "center" }}>
          {quoteCreated ? "Quote ready — link shown in chat." : "Chat saved automatically."}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={handleShareCurrentLink}
            style={{
              background: "transparent",
              color: "#374151",
              padding: "8px 12px",
              borderRadius: 8,
              border: "1px solid #e5e7eb",
              cursor: "pointer"
            }}
          >
            Share
          </button>
        </div>
      </div>
    </div>
  );
}