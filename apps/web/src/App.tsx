import { useEffect, useState } from "react";

type ModuleInfo = {
  id: string;
  title: string;
  status: string;
  priority: string;
};

type MetaResponse = {
  name: string;
  version: string;
  env: string;
  vram_profile: string;
  llm: {
    base_url: string;
    model: string;
    num_ctx: number;
    keep_alive: string;
  };
  modules: ModuleInfo[];
};

type HealthResponse = {
  status: string;
  service: string;
  version: string;
  timestamp: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [healthRes, metaRes] = await Promise.all([
          fetch(`${API_BASE}/health`),
          fetch(`${API_BASE}/api/meta`),
        ]);
        if (!healthRes.ok || !metaRes.ok) {
          throw new Error(`API 响应异常: ${healthRes.status} / ${metaRes.status}`);
        }
        const healthJson = (await healthRes.json()) as HealthResponse;
        const metaJson = (await metaRes.json()) as MetaResponse;
        if (!cancelled) {
          setHealth(healthJson);
          setMeta(metaJson);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "无法连接 API");
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page">
      <header className="hero">
        <p className="eyebrow">Local multi-capability agent</p>
        <h1>AgentTest</h1>
        <p className="lede">
          对话是主入口之一：人设、记忆与语音。桌面、办公、网页研究、会议与 Skills
          将逐步落地。当前为 Docker 骨架版本。
        </p>
      </header>

      <section className="panel">
        <h2>服务状态</h2>
        {error ? (
          <p className="error">API 未就绪：{error}</p>
        ) : (
          <dl className="facts">
            <div>
              <dt>Health</dt>
              <dd>{health?.status ?? "…"}</dd>
            </div>
            <div>
              <dt>版本</dt>
              <dd>{health?.version ?? meta?.version ?? "…"}</dd>
            </div>
            <div>
              <dt>VRAM 档位</dt>
              <dd>{meta?.vram_profile ?? "…"}</dd>
            </div>
            <div>
              <dt>LLM 模型</dt>
              <dd>{meta?.llm.model ?? "…"}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="panel">
        <h2>功能模块</h2>
        <ul className="modules">
          {(meta?.modules ?? []).map((m) => (
            <li key={m.id}>
              <span className="module-title">{m.title}</span>
              <span className="module-meta">
                {m.priority} · {m.status}
              </span>
            </li>
          ))}
          {!meta && !error ? <li>加载中…</li> : null}
        </ul>
      </section>
    </div>
  );
}
