import React from "react";
import { Routes, Route } from "react-router-dom";
import { ChatSidebar } from "../components/ChatSidebar";
import { ChatPage } from "./ChatPage";
import { ChatHome } from "./ChatHome";

export function ChatLayout() {
  return (
    <div style={{ display: 'flex', height: '100%', width: '100%' }}>
      <ChatSidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        <Routes>
          <Route path="/" element={<ChatHome />} />
          <Route path="/:session_id" element={<ChatPage />} />
        </Routes>
      </div>
    </div>
  );
}
