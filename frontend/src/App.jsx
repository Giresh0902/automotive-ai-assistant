import { useState } from "react";
import Documents from "./pages/Documents.jsx";
import Chat from "./pages/Chat.jsx";

export default function App() {
  const [tab, setTab] = useState("chat");
  return (
    <div className="app">
      <header>
        <h1>🚗 Automotive AI Assistant</h1>
        <nav>
          <button className={tab === "chat" ? "on" : ""} onClick={() => setTab("chat")}>Chat</button>
          <button className={tab === "docs" ? "on" : ""} onClick={() => setTab("docs")}>Documents (Admin)</button>
        </nav>
      </header>
      <main>{tab === "chat" ? <Chat /> : <Documents />}</main>
    </div>
  );
}
