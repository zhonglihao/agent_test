# WorldSim — 最小可 tick + 免费搜索学习 + 2.5D 场景

对齐 Project 契约的 **路径 A** 骨架：无 LLM key 可 tick；**默认 DuckDuckGo Instant Answer**（免 key）自主学习；**2.5D** 六地点舞台；可选本机 SearXNG。

## 与文档对应

| 文档（Project store `docs/`） | 本包落点 |
| --- | --- |
| `data-contract-v0.md` | `worldsim/models.py` |
| `world-pack-v0.md` | `worldsim/seed.py` |
| `protagonist-implementation.md` | `worldsim/tick.py` |
| `emotion-simulation.md` | `worldsim/affect.py` |
| `autonomous-web-learning.md` | `worldsim/learn.py` + `worldsim/search/` |
| `search-and-scene-viz.md` | 搜索栈 + `web/scene.js` 2.5D |
| `api-provider-recommendation.md` | `config.example.yaml` LLM 段 |

## 配置

```bash
cd apps/sim
cp config.example.yaml config.yaml   # gitignored；勿提交真实 key
```

### 搜索（已定死默认三方）

| 项 | 值 |
| --- | --- |
| **默认 Provider** | `search.default_provider: duckduckgo` |
| **端点** | `https://api.duckduckgo.com/`（Instant Answer JSON，**免 key**） |
| **补充** | `providers.wikimedia` → `https://zh.wikipedia.org/w/api.php`（免 key） |
| **离线兜底** | `providers.local_knowledge`（网络空结果时） |
| **可选 SERP** | `providers.searxng` 默认 **关闭**；本机 Docker 时可开 |

Instant Answer **不是**完整网页 SERP；许多查询 Abstract 为空，此时会降级 Wikimedia → local。展示摘要时请署名 DuckDuckGo；遵守 [DuckDuckGo Terms](https://duckduckgo.com/terms)，勿高频滥用。

LLM：`deepseek_api_key` / `dashscope_api_key` 可留空（跳过 LLM）。

### 可选：本机 SearXNG（不租 VPS）

```bash
cd apps/sim
docker compose -f docker-compose.searxng.yml up -d
# 浏览器 http://127.0.0.1:8080
```

在 `config.yaml`：

```yaml
search:
  providers:
    searxng:
      enabled: true
      base_url: http://127.0.0.1:8080
```

启用后栈优先序：`searxng` → `duckduckgo` → `wikimedia` → `local_knowledge`。

## 安装与运行

```bash
cd apps/sim
pip install -r requirements.txt -t .deps   # 或 venv
export PYTHONPATH="$(pwd):$(pwd)/.deps"

python -m worldsim seed
python -m worldsim tick -n 16
python -m worldsim snapshot
python -m worldsim serve   # http://127.0.0.1:8100/ 含 2.5D 页
```

### 只读 HTTP

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | 2.5D 观测页 |
| GET | `/world/snapshot?agent_id=` | 含 locations.**edges**、学习摘要 |
| GET | `/world/graph?agent_id=` | 地点图 |
| GET | `/memories?agent_id=&q=&source=` | S3 过滤；`source=external_learn` |
| GET | `/affect/trajectory?agent_id=` | PAD |
| POST | `/debug/tick?n=` | 调试推进 |
| 写记忆/PAD | | **403** |

### 验默认 DuckDuckGo（网络允许时）

```bash
PYTHONPATH="$(pwd):$(pwd)/.deps" python -c "
from worldsim.search.providers import DuckDuckGoProvider
hits = DuckDuckGoProvider().retrieve('Python (programming language)', 2)
print([(h.provider, h.title[:40], bool(h.snippet)) for h in hits])
"
```

有网时应看到 `provider=duckduckgo` 与非空 snippet。

## 无 LLM / 无付费搜索行为

- 日志：`SearchProvider 栈已接线：default=duckduckgo order=[...]`
- 好奇/缺口 tick：真实请求 DDG Instant Answer；空则 Wikimedia / local
- 写入记忆 `source=external_learn`（trust=unverified；不改 world.weather）

## 2.5D 场景

- `web/scene.js`：伪透视地点砖 + 主角 ★ + 日段天空；吃 snapshot
- 后期真 3D：snapshot 含 `scene_renderer_v2_note`，**未实现**

## 已知限制

- Instant Answer 覆盖有限；全网 SERP 请开本机 SearXNG
- Intent / Commitment / 外部神改天气 UI 未做
- ProfileMerge 学习→画像后置
- 与 `apps/api` 聊天栈并行共存
