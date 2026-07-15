from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings


class DesktopError(RuntimeError):
    pass


class DesktopService:
    """Sandboxed file tools. Shell execution is intentionally deferred."""

    def __init__(self, workspace: Path | None = None) -> None:
        settings = get_settings()
        root = workspace or Path(settings.data_dir) / "workspace"
        self.workspace = root.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative: str) -> Path:
        rel = relative.strip().replace("\\", "/")
        if rel.startswith("/"):
            rel = rel[1:]
        target = (self.workspace / rel).resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError as exc:
            raise DesktopError("路径越界：仅允许访问 workspace 目录") from exc
        return target

    def list_dir(self, relative: str = ".") -> list[dict[str, Any]]:
        path = self._resolve(relative)
        if not path.exists():
            raise DesktopError(f"目录不存在：{relative}")
        if not path.is_dir():
            raise DesktopError(f"不是目录：{relative}")
        items: list[dict[str, Any]] = []
        for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            stat = child.stat()
            items.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(self.workspace)).replace("\\", "/"),
                    "type": "dir" if child.is_dir() else "file",
                    "size": 0 if child.is_dir() else stat.st_size,
                }
            )
        return items

    def read_file(self, relative: str, max_bytes: int = 200_000) -> dict[str, Any]:
        path = self._resolve(relative)
        if not path.exists() or not path.is_file():
            raise DesktopError(f"文件不存在：{relative}")
        data = path.read_bytes()
        truncated = len(data) > max_bytes
        text = data[:max_bytes].decode("utf-8", errors="replace")
        return {
            "path": relative.replace("\\", "/"),
            "size": len(data),
            "truncated": truncated,
            "content": text,
        }

    def write_file(self, relative: str, content: str, overwrite: bool = True) -> dict[str, Any]:
        path = self._resolve(relative)
        if path.exists() and not overwrite:
            raise DesktopError("文件已存在，且 overwrite=false")
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        path.write_bytes(encoded)
        return {
            "path": str(path.relative_to(self.workspace)).replace("\\", "/"),
            "size": len(encoded),
        }

    def info(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace),
            "repo_root": str(REPO_ROOT),
            "shell_enabled": False,
        }
