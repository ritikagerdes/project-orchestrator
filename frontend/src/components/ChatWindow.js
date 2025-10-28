import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

export default function ChatWindow({ onClose, position = "bottom-right", mode = "production" }) {
  const [messages, setMessages] = useState([
    { from: "bot", text: "Hi — describe your project and I'll help estimate it." }
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingQuestions, setPendingQuestions] = useState([]); // array of clarification questions from server
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [answers, setAnswers] = useState([]); // collected answers in order
  const [lastUserQuery, setLastUserQuery] = useState(""); // original user text for follow-up
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, pendingQuestions, currentQIndex]);

  // helper to append a message
  const pushMessage = (m) => setMessages(prev => [...prev, m]);

  async function sendInitial(text) {
    setSending(true);
    try {
      const res = await axios.post("/api/message", { text, client_info: {}, mode });
      const data = res.data;
      // If server provided an array of clarification questions, start sequential flow
      if (Array.isArray(data.questions) && data.questions.length > 0) {
        setPendingQuestions(data.questions);
        setCurrentQIndex(0);
        setAnswers([]);
        pushMessage({ from: "bot", text: data.questions[0] });
      } else if (data.requires_clarification && Array.isArray(data.questions)) {
        setPendingQuestions(data.questions);
        setCurrentQIndex(0);
        setAnswers([]);
        pushMessage({ from: "bot", text: data.questions[0] });
      } else {
        // handle completed / other responses as before
        if (data.status === "completed") {
          const sowText = data.sow ? (typeof window !== "undefined" ? atob(data.sow) : "") : "";
          pushMessage({ from: "bot", text: data.summary || "Estimate complete." });
          if (data.estimate?.totalCost) pushMessage({ from: "bot", text: `Total cost: ${data.estimate.totalCost}` });
          if (sowText) pushMessage({ from: "bot", text: sowText });
        } else if (data.questions && !Array.isArray(data.questions)) {
          pushMessage({ from: "bot", text: JSON.stringify(data.questions) });
        } else {
          pushMessage({ from: "bot", text: JSON.stringify(data) });
        }
      }
    } catch (err) {
      pushMessage({ from: "bot", text: "Error contacting server." });
    } finally {
      setSending(false);
    }
  }

  // when we've answered all pending questions, send aggregated follow-up to backend
  async function sendFollowUp() {
    setSending(true);
    try {
      const followPayload = {
        text: lastUserQuery,
        client_info: { answers }, // backend can read answers[] and continue
        mode
      };
      const res = await axios.post("/api/message", followPayload);
      const data = res.data;
      // clear pending/question state
      setPendingQuestions([]);
      setCurrentQIndex(0);
      setAnswers([]);
      // handle response similarly to initial
      if (data.status === "completed") {
        const sowText = data.sow ? (typeof window !== "undefined" ? atob(data.sow) : "") : "";
        pushMessage({ from: "bot", text: data.summary || "Estimate complete." });
        if (data.estimate?.totalCost) pushMessage({ from: "bot", text: `Total cost: ${data.estimate.totalCost}` });
        if (sowText) pushMessage({ from: "bot", text: sowText });
      } else if (Array.isArray(data.questions) && data.questions.length > 0) {
        // backend still needs clarification -> restart sequential flow
        setPendingQuestions(data.questions);
        setCurrentQIndex(0);
        pushMessage({ from: "bot", text: data.questions[0] });
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

    // if there is an active sequential question flow, treat this input as answer to current question
    if (pendingQuestions.length > 0) {
      // push user's answer
      pushMessage({ from: "user", text });
      setAnswers(prev => [...prev, { question: pendingQuestions[currentQIndex], answer: text }]);
      setInput("");

      // if more questions remain, show next question only
      if (currentQIndex + 1 < pendingQuestions.length) {
        const nextIndex = currentQIndex + 1;
        setCurrentQIndex(nextIndex);
        pushMessage({ from: "bot", text: pendingQuestions[nextIndex] });
      } else {
        // finished Qs -> send aggregated follow-up to backend
        await sendFollowUp();
      }
      return;
    }

    // no pending questions: this is a new initial message
    pushMessage({ from: "user", text });
    setInput("");
    setLastUserQuery(text);
    await sendInitial(text);
  }

  return (
    <div className={`chat-window ${position === "bottom-left" ? "chat-btn-left" : "chat-btn-right"}`}>
      <div style={{ padding: 8, borderBottom: "1px solid #eee", background: "#fff" }}>
        <strong>Sales chat ({mode})</strong>
        <button style={{ float: "right" }} onClick={onClose}>Close</button>
      </div>

      <div ref={listRef} style={{ padding: 12, height: 260, overflowY: "auto", background: "#f7fbff" }}>
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 8, textAlign: m.from === "user" ? "right" : "left" }}>
            <div style={{ display: "inline-block", padding: "8px 10px", borderRadius: 8, background: m.from === "user" ? "#e2e8f0" : "#fff" }}>
              {m.text}
            </div>
          </div>
        ))}
      </div>

      <div style={{ padding: 8, borderTop: "1px solid #eee", background: "#fff", display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={pendingQuestions.length > 0 ? "Answer the question..." : "Describe your project..."}
          style={{ flex: 1 }}
          onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
        />
        <button onClick={handleSend} disabled={sending}>{sending ? "..." : "Send"}</button>
      </div>
    </div>
  );
}