# WorldSim — 最小可 tick 世界模拟（路径 A）

对齐 Project 文档契约的 **P0 骨架**：无 LLM 也能推进时钟 / 位置 / 精力、模板情景记忆、规则 ΔPAD；可选接 DeepSeek Flash（结构化）+ 百炼 Qwen-Plus（叙事），**无 key 时跳过**。

## 与文档对应

| 文档（Project store `docs/`） | 本包落点 |
| --- | --- |
| `data-contract-v0.md` | `worldsim/models.py` |
| `world-pack-v0.md` | `worldsim/seed.py`（6 地点 + `agent_seed_01`） |
| `protagonist-implementation.md` | `worldsim/tick.py` — `tick(state, agent_id)` |
| `emotion-simulation.md` | `worldsim/affect.py` — 唯一 `affect_step` |
| `long-term-memory-forgetting.md` | `worldsim/memory.py` — 写入闸门 + 模板日记 |
| `api-provider-recommendation.md` | `config.example.yaml` + `worldsim/llm.py` |

仓库路径：`apps/sim/`。

## 配置

```bash
cd apps/sim
cp config.example.yaml config.yaml   # config.yaml 已进 .gitignore
# 可暂留 deepseek_api_key / dashscope_api_key 为空字符串
```

字段说明见 `config.example.yaml`。真实密钥只写本地 `config.yaml` / `.env`，**不要提交仓库**。

## 安装与运行

```bash
cd apps/sim
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 初始化 seed
python -m worldsim seed

# 推进一步 / 多步
python -m worldsim tick
python -m worldsim tick -n 16

# 打印快照
python -m worldsim snapshot

# 只读 API（默认 127.0.0.1:8100）
python -m worldsim serve
```

### 只读 HTTP

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/world/snapshot?agent_id=agent_seed_01` | 世界 + agent 快照 |
| GET | `/memories?agent_id=…` | 情景记忆（按 agent 过滤） |
| GET | `/affect/trajectory?agent_id=…` | PAD 轨迹 |
| GET | `/requests?agent_id=…` | Intent 占位（P0 空） |
| POST | `/debug/tick?n=1&agent_id=…` | 调试推进（非用户写记忆） |

对 `/memories`、`/affect*` 的写方法返回 **403**。

极简观测页：启动 API 后打开 `web/index.html`（或用任意静态服务器）。

## 无 key 行为

日志会出现：

```text
跳过 LLM（structured / Flash）：无 deepseek_api_key，使用规则层
跳过 LLM（narrative / Plus）：无 dashscope_api_key，使用模板叙事
```

规则层仍会：推进 `SimClock`（默认 +30 模拟分钟）、按作息移动最多 1 边、更新 `energy`/`hunger`、写模板记忆、经 `affect_step` 写 `affect_log`。

## 状态文件

默认：`data/worldsim/state.json`（相对仓库根，由 `config.data_dir` 解析）。`data/*` 已 gitignore。

## 已知限制（P0）

- 无 Intent / Commitment 闭环（C5–C6）
- 无外部神改天气 UI（可用手改 `state.json` 的 `weather` 验收）
- LLM 接口已预留，有 key 时仍先走规则（完整 cognize 后续）
- 与仓库原有 `apps/api` 聊天 Agent **并行共存**，未合并编排
