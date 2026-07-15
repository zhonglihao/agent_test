from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import Settings, get_settings
from app.db.sqlite import Database
from app.services.llm import LLMClient, LLMError
from app.services.persona import CharacterPack, PersonaService
from app.services.tools import ToolRuntime

REMEMBER_RE = re.compile(r"^(?:记住|請記住|请记住)[:：]\s*(.+)$")
FORGET_RE = re.compile(r"^(?:忘掉|忘记|忘記)[:：]\s*(.+)$")
MAX_TOOL_ROUNDS = 4


class ChatService:
    def __init__(
        self,
        db: Database | None = None,
        llm: LLMClient | None = None,
        personas: PersonaService | None = None,
        tools: ToolRuntime | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db = db or Database()
        self.llm = llm or LLMClient(self.settings)
        self.personas = personas or PersonaService()
        self.tools = tools or ToolRuntime()

    def memory_scope_key(self, pack: CharacterPack) -> str:
        if pack.memory_scope == "private":
            return f"persona:{pack.id}"
        return "shared"

    def build_messages(
        self,
        session: dict[str, Any],
        pack: CharacterPack,
        history: list[dict[str, Any]],
        *,
        tools_enabled: bool,
    ) -> list[dict[str, Any]]:
        system_parts = [pack.build_system_prompt()]
        if tools_enabled:
            info = self.tools.desktop.info()
            system_parts.append(
                "你可以使用桌面文件工具，作用域仅限沙箱工作区："
                f"{info['workspace']}。"
                "相对路径如 notes/todo.txt。写文件前先确认路径；"
                "完成后用简洁中文说明你做了什么。"
            )
        memories = self.db.list_memories(self.memory_scope_key(pack))
        if memories:
            bullets = "\n".join(f"- {m['content']}" for m in memories[:30])
            system_parts.append(f"长期记忆：\n{bullets}")
        summary = (session.get("summary") or "").strip()
        if summary:
            system_parts.append(f"更早对话摘要：\n{summary}")

        working_limit = self.settings.chat_working_turns * 2
        recent = history[-working_limit:] if working_limit > 0 else history
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "\n\n".join(system_parts)}
        ]
        for item in recent:
            role = item["role"]
            if role not in {"user", "assistant", "system"}:
                continue
            messages.append({"role": role, "content": item["content"]})
        return messages

    def handle_memory_command(
        self, user_text: str, pack: CharacterPack
    ) -> dict[str, Any] | None:
        text = user_text.strip()
        remember = REMEMBER_RE.match(text)
        if remember:
            content = remember.group(1).strip()
            memory = self.db.add_memory(self.memory_scope_key(pack), content)
            return {
                "type": "remember",
                "reply": f"已记住：{content}",
                "memory": memory,
            }
        forget = FORGET_RE.match(text)
        if forget:
            keyword = forget.group(1).strip()
            deleted = self.db.delete_memories_matching(
                self.memory_scope_key(pack), keyword
            )
            return {
                "type": "forget",
                "reply": f"已尝试忘掉与「{keyword}」相关的记忆（删除 {deleted} 条）。",
                "deleted": deleted,
            }
        return None

    async def maybe_summarize(self, session_id: str, pack: CharacterPack) -> None:
        session = self.db.get_session(session_id)
        if not session:
            return
        count = self.db.count_messages(session_id)
        if count < self.settings.chat_summarize_after_turns * 2:
            return
        history = self.db.list_messages(session_id)
        keep = self.settings.chat_working_turns * 2
        older = history[:-keep] if keep < len(history) else []
        if len(older) < 4:
            return
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in older[-40:])
        prompt = [
            {
                "role": "system",
                "content": (
                    "请把对话压缩成简洁中文摘要，保留人物偏好、约定与未完成事项。"
                    f"不超过 {self.settings.chat_max_summary_chars} 字。"
                ),
            },
            {
                "role": "user",
                "content": f"已有摘要：\n{session.get('summary') or '（无）'}\n\n"
                f"新增对话：\n{transcript}",
            },
        ]
        try:
            summary = await self.llm.complete_text(prompt, temperature=0.2)
        except LLMError:
            return
        if summary:
            self.db.update_session(
                session_id, summary=summary[: self.settings.chat_max_summary_chars]
            )

    async def stream_reply(
        self,
        session_id: str,
        user_text: str,
        *,
        persona_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        session = self.db.get_session(session_id)
        if not session:
            yield {"event": "error", "data": {"message": "会话不存在"}}
            return

        if persona_id and persona_id != session.get("persona_id"):
            session = self.db.update_session(session_id, persona_id=persona_id) or session

        pack = self.personas.get_pack(session.get("persona_id"))
        self.db.add_message(session_id, "user", user_text)

        if self.db.count_messages(session_id) == 1 and session.get("title") == "新对话":
            title = user_text.strip().replace("\n", " ")[:24] or "新对话"
            self.db.update_session(session_id, title=title)

        memory_cmd = self.handle_memory_command(user_text, pack)
        if memory_cmd:
            reply = memory_cmd["reply"]
            self.db.add_message(session_id, "assistant", reply)
            yield {
                "event": "meta",
                "data": {"persona_id": pack.id, "memory": memory_cmd["type"]},
            }
            yield {"event": "token", "data": {"content": reply}}
            yield {
                "event": "done",
                "data": {"session_id": session_id, "persona_id": pack.id},
            }
            return

        tool_schemas = self.tools.schemas_for_level(pack.boundaries.tools)
        history = self.db.list_messages(session_id)
        messages = self.build_messages(
            session, pack, history, tools_enabled=bool(tool_schemas)
        )
        yield {
            "event": "meta",
            "data": {
                "persona_id": pack.id,
                "model": self.settings.llm_model,
                "tools": [t["function"]["name"] for t in tool_schemas],
            },
        }

        try:
            if tool_schemas:
                async for event in self._run_with_tools(
                    messages, pack, tool_schemas, session_id
                ):
                    yield event
            else:
                async for event in self._stream_plain(messages, pack, session_id):
                    yield event
        except LLMError as exc:
            yield {"event": "error", "data": {"message": str(exc)}}

    async def _stream_plain(
        self,
        messages: list[dict[str, Any]],
        pack: CharacterPack,
        session_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        buffer: list[str] = []
        async for token in self.llm.stream_chat(
            messages, temperature=pack.sampling.temperature
        ):
            buffer.append(token)
            yield {"event": "token", "data": {"content": token}}
        full = "".join(buffer).strip()
        if not full:
            full = "（模型没有返回内容，请检查 Ollama 是否已启动并拉取对应模型。）"
            yield {"event": "token", "data": {"content": full}}
        self.db.add_message(session_id, "assistant", full)
        await self.maybe_summarize(session_id, pack)
        yield {
            "event": "done",
            "data": {"session_id": session_id, "persona_id": pack.id},
        }

    async def _run_with_tools(
        self,
        messages: list[dict[str, Any]],
        pack: CharacterPack,
        tool_schemas: list[dict[str, Any]],
        session_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        working = list(messages)
        for _ in range(MAX_TOOL_ROUNDS):
            message = await self.llm.complete_message(
                working,
                temperature=pack.sampling.temperature,
                tools=tool_schemas,
            )
            tool_calls = message.get("tool_calls") or []
            content = str(message.get("content") or "")
            if tool_calls:
                working.append(
                    {
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": tool_calls,
                    }
                )
                for call in tool_calls:
                    fn = call.get("function") or {}
                    name = str(fn.get("name") or "")
                    raw_args = fn.get("arguments") or {}
                    call_id = str(call.get("id") or name)
                    yield {
                        "event": "tool_start",
                        "data": {"name": name, "arguments": raw_args},
                    }
                    result = self.tools.execute(name, raw_args)
                    payload = json.dumps(result, ensure_ascii=False)
                    yield {
                        "event": "tool_result",
                        "data": {"name": name, "result": result},
                    }
                    working.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": name,
                            "content": payload,
                        }
                    )
                continue

            # No more tools: stream a polished final answer (optionally reuse content)
            if content.strip():
                yield {"event": "token", "data": {"content": content}}
                self.db.add_message(session_id, "assistant", content.strip())
                await self.maybe_summarize(session_id, pack)
                yield {
                    "event": "done",
                    "data": {"session_id": session_id, "persona_id": pack.id},
                }
                return

            # Empty content without tools — ask for a final streamed reply
            async for event in self._stream_plain(working, pack, session_id):
                yield event
            return

        # Safety stop after max rounds
        final = "已达到工具调用轮次上限。请根据已有结果继续说明，或换个更具体的请求。"
        yield {"event": "token", "data": {"content": final}}
        self.db.add_message(session_id, "assistant", final)
        yield {
            "event": "done",
            "data": {"session_id": session_id, "persona_id": pack.id},
        }
