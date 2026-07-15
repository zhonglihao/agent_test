from __future__ import annotations

import json
from typing import Any, Callable

from app.services.desktop import DesktopError, DesktopService


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


DESKTOP_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "workspace_info",
            "description": "查看沙箱工作区路径与能力说明（桌面文件工具仅限该目录）。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出工作区内某目录的文件与子目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对工作区路径，默认 '.'",
                        "default": ".",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取工作区内文本文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对工作区的文件路径",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入工作区内文本文件（可创建父目录）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对工作区文件路径"},
                    "content": {"type": "string", "description": "要写入的文本内容"},
                    "overwrite": {
                        "type": "boolean",
                        "description": "是否覆盖已存在文件，默认 true",
                        "default": True,
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolRuntime:
    def __init__(self, desktop: DesktopService | None = None) -> None:
        self.desktop = desktop or DesktopService()

    def schemas_for_level(self, level: str) -> list[dict[str, Any]]:
        level = (level or "none").lower()
        if level in {"none", "off", "false", "0"}:
            return []
        names = {"workspace_info", "list_dir", "read_file"}
        if level in {"full", "write", "all"}:
            names.add("write_file")
        return [
            schema
            for schema in DESKTOP_TOOL_SCHEMAS
            if schema["function"]["name"] in names
        ]

    def execute(self, name: str, arguments: dict[str, Any] | str | None) -> dict[str, Any]:
        args = self._parse_args(arguments)
        try:
            if name == "workspace_info":
                return {"ok": True, "result": self.desktop.info()}
            if name == "list_dir":
                path = str(args.get("path") or ".")
                return {"ok": True, "result": self.desktop.list_dir(path)}
            if name == "read_file":
                path = str(args.get("path") or "")
                if not path:
                    return {"ok": False, "error": "path 不能为空"}
                return {"ok": True, "result": self.desktop.read_file(path)}
            if name == "write_file":
                path = str(args.get("path") or "")
                content = str(args.get("content") or "")
                overwrite = bool(args.get("overwrite", True))
                if not path:
                    return {"ok": False, "error": "path 不能为空"}
                return {
                    "ok": True,
                    "result": self.desktop.write_file(path, content, overwrite),
                }
            return {"ok": False, "error": f"未知工具：{name}"}
        except DesktopError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"工具执行异常：{exc}"}

    def _parse_args(self, arguments: dict[str, Any] | str | None) -> dict[str, Any]:
        if arguments is None:
            return {}
        if isinstance(arguments, dict):
            return arguments
        text = str(arguments).strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
