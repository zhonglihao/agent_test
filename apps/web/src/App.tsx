import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Persona = {
  id: string;
  name: string;
  description: string;
  greeting: string;
};

type Session = {
  id: string;
  title: string;
  persona_id: string | null;
  updated_at: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
};

async function readSse(
  response: Response,
  onEvent: (event: string, data: Record<string, unknown>) => void,
) {
  if (!response.body) {
    throw new Error("浏览器不支持流式响应");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let eventName = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n");
    buffer = chunks.pop() ?? "";
    for (const rawLine of chunks) {
      const line = rawLine.replace(/\r$/, "");
      if (!line) {
        eventName = "message";
        continue;
      }
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (line.startsWith("data:")) {
        const payload = line.slice(5).trim();
        try {
          onEvent(eventName, JSON.parse(payload) as Record<string, unknown>);
        } catch {
          // ignore malformed chunk
        }
      }
    }
  }
}

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [personaId, setPersonaId] = useState<string>("assistant-default");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("连接中…");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const activePersona = useMemo(
    () => personas.find((p) => p.id === personaId) ?? personas[0],
    [personas, personaId],
  );

  const refreshSessions = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/chat/sessions`);
    if (!res.ok) throw new Error("无法加载会话列表");
    const data = (await res.json()) as { items: Session[] };
    setSessions(data.items);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      try {
        const [healthRes, personaRes] = await Promise.all([
          fetch(`${API_BASE}/health`),
          fetch(`${API_BASE}/api/personas`),
        ]);
        if (!healthRes.ok) throw new Error("API 健康检查失败");
        const personaData = (await personaRes.json()) as { items: Persona[] };
        if (cancelled) return;
        setPersonas(personaData.items);
        if (personaData.items[0]) setPersonaId(personaData.items[0].id);
        setStatus("在线");
        await refreshSessions();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "启动失败");
          setStatus("离线");
        }
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [refreshSessions]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function openSession(id: string) {
    const res = await fetch(`${API_BASE}/api/chat/sessions/${id}`);
    if (!res.ok) {
      setError("无法打开会话");
      return;
    }
    const data = (await res.json()) as {
      session: Session;
      messages: ChatMessage[];
    };
    setSessionId(data.session.id);
    setPersonaId(data.session.persona_id || personaId);
    setMessages(data.messages);
    setError(null);
  }

  async function createSession() {
    const res = await fetch(`${API_BASE}/api/chat/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona_id: personaId }),
    });
    if (!res.ok) {
      setError("创建会话失败");
      return;
    }
    const session = (await res.json()) as Session;
    await refreshSessions();
    setSessionId(session.id);
    setMessages([]);
    if (activePersona?.greeting) {
      setMessages([
        {
          id: "greeting",
          role: "assistant",
          content: activePersona.greeting,
        },
      ]);
    }
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    setInput("");

    let currentSessionId = sessionId;
    if (!currentSessionId) {
      const res = await fetch(`${API_BASE}/api/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona_id: personaId }),
      });
      if (!res.ok) {
        setError("创建会话失败");
        setBusy(false);
        return;
      }
      const session = (await res.json()) as Session;
      currentSessionId = session.id;
      setSessionId(session.id);
    }

    const userMsg: ChatMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: text,
    };
    const assistantId = `local-assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev.filter((m) => m.id !== "greeting"),
      userMsg,
      { id: assistantId, role: "assistant", content: "" },
    ]);

    try {
      const res = await fetch(
        `${API_BASE}/api/chat/sessions/${currentSessionId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, persona_id: personaId }),
        },
      );
      if (!res.ok) {
        throw new Error(`发送失败 (${res.status})`);
      }
      await readSse(res, (event, data) => {
        if (event === "token" && typeof data.content === "string") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + data.content }
                : m,
            ),
          );
        }
        if (event === "error" && typeof data.message === "string") {
          setError(data.message);
        }
      });
      await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <p className="eyebrow">AgentTest</p>
          <h1>对话</h1>
          <p className="status">API {status}</p>
        </div>

        <label className="field">
          <span>角色</span>
          <select
            value={personaId}
            onChange={(e) => setPersonaId(e.target.value)}
            disabled={busy}
          >
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <button className="primary" type="button" onClick={() => void createSession()}>
          新建会话
        </button>

        <ul className="session-list">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className={s.id === sessionId ? "active" : ""}
                onClick={() => void openSession(s.id)}
              >
                {s.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="chat">
        <header className="chat-header">
          <div>
            <h2>{activePersona?.name ?? "助手"}</h2>
            <p>{activePersona?.description || "本地多轮对话 · 分层记忆"}</p>
          </div>
        </header>

        <div className="messages">
          {messages.length === 0 ? (
            <div className="empty">
              <p>{activePersona?.greeting || "发送一条消息开始对话。"}</p>
              <p className="hint">试试：记住：我喜欢简洁回答</p>
            </div>
          ) : (
            messages.map((m) => (
              <article key={m.id} className={`bubble ${m.role}`}>
                <p>{m.content || (busy && m.role === "assistant" ? "…" : "")}</p>
              </article>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {error ? <p className="error">{error}</p> : null}

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            void sendMessage();
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入消息，Enter 发送（Shift+Enter 换行）"
            rows={3}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendMessage();
              }
            }}
          />
          <button className="primary" type="submit" disabled={busy || !input.trim()}>
            {busy ? "生成中…" : "发送"}
          </button>
        </form>
      </main>
    </div>
  );
}
