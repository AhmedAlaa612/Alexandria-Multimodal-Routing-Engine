import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import AlOstaAgent


load_dotenv()

app = FastAPI(title="Al-Osta UI")

# Simple in-memory session store: session_id -> agent instance
_agents: dict[str, AlOstaAgent] = {}
_agent_keys: dict[str, str] = {}


class ChatRequest(BaseModel):
    message: str
    api_key: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str


class ResetRequest(BaseModel):
    session_id: str


def _resolve_key(provided_key: Optional[str]) -> Optional[str]:
    if provided_key and provided_key.strip():
        return provided_key.strip()
    return os.getenv("GEMINI_API_KEY")


def _get_or_create_agent(session_id: str, api_key: str) -> AlOstaAgent:
  current_key = _agent_keys.get(session_id)
  if session_id not in _agents or current_key != api_key:
    _agents[session_id] = AlOstaAgent(api_key)
    _agent_keys[session_id] = api_key
  return _agents[session_id]


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Al-Osta Agent Tester</title>
  <style>
    :root {
      --bg: #f2f4f8;
      --panel: #ffffff;
      --text: #16202a;
      --muted: #67717f;
      --brand: #0f766e;
      --brand-2: #115e59;
      --border: #d8dee6;
      --user: #ecfeff;
      --bot: #f8fafc;
      --danger: #b91c1c;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      background: radial-gradient(circle at top left, #dbeafe 0%, var(--bg) 45%, #ecfeff 100%);
      color: var(--text);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 20px;
    }

    .app {
      width: min(900px, 100%);
      height: min(88vh, 860px);
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      overflow: hidden;
      box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
    }

    .header {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      display: grid;
      gap: 10px;
      background: linear-gradient(90deg, #f0fdfa 0%, #eff6ff 100%);
    }

    .title {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      color: var(--brand-2);
    }

    .row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: center;
    }

    input, textarea, button {
      font: inherit;
    }

    #apiKey {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      background: #fff;
      color: var(--text);
    }

    .chat {
      padding: 14px;
      overflow-y: auto;
      display: grid;
      gap: 10px;
      align-content: start;
      background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    }

    .msg {
      max-width: 85%;
      border-radius: 12px;
      padding: 10px 12px;
      border: 1px solid var(--border);
      white-space: pre-wrap;
      line-height: 1.45;
      word-break: break-word;
    }

    .user {
      justify-self: end;
      background: var(--user);
    }

    .bot {
      justify-self: start;
      background: var(--bot);
    }

    .composer {
      border-top: 1px solid var(--border);
      padding: 12px;
      display: grid;
      gap: 10px;
    }

    #message {
      width: 100%;
      min-height: 72px;
      max-height: 180px;
      resize: vertical;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      background: #fff;
      color: var(--text);
    }

    .actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    button {
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      cursor: pointer;
      color: #fff;
      background: var(--brand);
      transition: transform 120ms ease, opacity 120ms ease;
    }

    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.65; cursor: not-allowed; }

    #resetBtn { background: var(--danger); }

    .hint {
      color: var(--muted);
      font-size: 13px;
      margin: 0;
    }
  </style>
</head>
<body>
  <main class="app">
    <section class="header">
      <h1 class="title">Al-Osta Agent Tester</h1>
      <div class="row">
        <input id="apiKey" type="password" placeholder="GEMINI_API_KEY (optional if set in .env)" />
        <button id="resetBtn" type="button">Reset Chat</button>
      </div>
      <p class="hint">Tip: Press Enter to send. Use Shift+Enter for a new line.</p>
    </section>

    <section id="chat" class="chat"></section>

    <section class="composer">
      <textarea id="message" placeholder="Type your message here..."></textarea>
      <div class="actions">
        <button id="sendBtn" type="button">Send</button>
      </div>
    </section>
  </main>

  <script>
    const chatEl = document.getElementById("chat");
    const messageEl = document.getElementById("message");
    const apiKeyEl = document.getElementById("apiKey");
    const sendBtn = document.getElementById("sendBtn");
    const resetBtn = document.getElementById("resetBtn");

    let sessionId = localStorage.getItem("al_osta_session_id") || null;

    function addMessage(role, text) {
      const div = document.createElement("div");
      div.className = `msg ${role}`;
      div.textContent = text;
      chatEl.appendChild(div);
      chatEl.scrollTop = chatEl.scrollHeight;
    }

    async function sendMessage() {
      const message = messageEl.value.trim();
      if (!message) return;

      addMessage("user", message);
      messageEl.value = "";
      sendBtn.disabled = true;

      try {
        const response = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            api_key: apiKeyEl.value.trim() || null,
            session_id: sessionId,
          }),
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Request failed");
        }

        sessionId = data.session_id;
        localStorage.setItem("al_osta_session_id", sessionId);
        addMessage("bot", data.answer || "No answer returned.");
      } catch (err) {
        addMessage("bot", `Error: ${err.message}`);
      } finally {
        sendBtn.disabled = false;
        messageEl.focus();
      }
    }

    async function resetChat() {
      if (sessionId) {
        await fetch("/reset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId }),
        });
      }

      sessionId = null;
      localStorage.removeItem("al_osta_session_id");
      chatEl.innerHTML = "";
      addMessage("bot", "Chat reset. Start a new conversation.");
    }

    sendBtn.addEventListener("click", sendMessage);
    resetBtn.addEventListener("click", resetChat);
    messageEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    addMessage("bot", "Ready. Send your first message.");
  </script>
</body>
</html>
"""


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    message = req.message.strip() if req.message else ""
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    api_key = _resolve_key(req.api_key)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Missing GEMINI_API_KEY. Provide it in the UI or set it in .env",
        )

    session_id = req.session_id or str(uuid.uuid4())

    try:
        agent = _get_or_create_agent(session_id, api_key)
        answer = agent.process_query(message)
        return ChatResponse(session_id=session_id, answer=answer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc


@app.post("/reset")
async def reset(req: ResetRequest) -> dict:
    _agents.pop(req.session_id, None)
    _agent_keys.pop(req.session_id, None)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("UI_PORT", "8085"))
    uvicorn.run("ui_app:app", host="0.0.0.0", port=port, reload=True)
