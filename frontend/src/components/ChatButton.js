import React, { useEffect, useState } from "react";
import ChatWindow from "./ChatWindow";
import axios from "axios";
import "./chat.css";

export default function ChatButton({ visible: propVisible, position: propPosition, mode }) {
  const [visible, setVisible] = useState(propVisible ?? true);
  const [position, setPosition] = useState(propPosition ?? "bottom-right");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof propVisible === "undefined" || typeof propPosition === "undefined") {
      axios.get("/api/admin/settings").then(res => {
        const s = res.data || {};
        if (typeof propVisible === "undefined") setVisible(Boolean(s.chat_enabled));
        if (typeof propPosition === "undefined") setPosition(s.chat_position || "bottom-right");
      }).catch(() => {
        // assume visible by default if settings fail
      });
    }
  }, [propVisible, propPosition]);

  if (!visible) return null;

  const posClass = position === "bottom-left" ? "chat-btn-left" : "chat-btn-right";

  return (
    <>
      <div className={`chat-button ${posClass}`} onClick={() => setOpen(v => !v)} role="button" aria-label="Open chat">
        <div className="chat-icon">💬</div>
        <div className="chat-label">Chat with Sales</div>
      </div>

      {open && <ChatWindow onClose={() => setOpen(false)} position={position} mode={mode} />}
    </>
  );
}