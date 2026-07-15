# AgentTest

本机多功能 AI Agent：**对话陪伴**（人设 / 记忆 / 语音）是核心能力之一，同时规划桌面管家、办公文档、网页研究、会议纪要与 Skills/MCP 扩展。

面向 **Windows + RTX 4060 Laptop 8GB**：默认 GPU 单飞、日常朗读走 edge-tts、本地音色克隆与 LLM **分时**占用显存。

## 快速开始（Docker）

### 前置

- Docker Desktop
- （推荐）本机安装 [Ollama](https://ollama.com)，并拉取模型：

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
# 更省显存：
# ollama pull qwen2.5:3b-instruct-q4_K_M
```

### 启动

```bash
cp .env.example .env
docker compose up --build -d
```

- Web UI: http://localhost:5173  
- API Docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

### 仅 API 开发热重载

```bash
docker compose up --build api
```

API 容器以只读方式挂载 `apps/api/app`，改代码后重启 `api` 服务即可验证。

## 仓库结构

```
apps/
  api/          # FastAPI 后端（Docker 内 Python 3.12）
  web/          # React + Vite + TypeScript
characters/     # Character Pack（示例在 _examples）
data/           # 运行时数据（SQLite 等，gitignore）
```

## 功能路线（摘要）

| 阶段 | 内容 |
|------|------|
| M0 | 骨架 → 对话记忆 → 角色包 → 语音 → 桌面工具 |
| M1 | WebUI 打磨、Skills、角色 zip |
| M2 | OfficeCLI、轻量网页研究 |
| M3 | 分时音色克隆、会议模式、MCP |

## VRAM 策略（4060 8GB）

- 默认模型：Qwen 7B Q4，`num_ctx=2048`
- 省显存档：3B Q4
- TTS 默认：edge-tts（0 显存）
- 克隆 TTS：可选插件，与 LLM **不要同时常驻 GPU**

## 许可

MIT（计划）
