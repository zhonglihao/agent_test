from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.core.config import get_settings


class VoiceConfig(BaseModel):
    mode: str = "preset"
    provider: str = "edge-tts"
    voice_id: str = "zh-CN-XiaoxiaoNeural"
    reference_path: str | None = None


class Boundaries(BaseModel):
    tools: str = "none"
    topics: list[str] = Field(default_factory=list)


class Sampling(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 1024


class CharacterPack(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    system_prompt: str
    style: str = ""
    greeting: str = ""
    boundaries: Boundaries = Field(default_factory=Boundaries)
    sampling: Sampling = Field(default_factory=Sampling)
    memory_scope: str = "shared"
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    path: str | None = None

    def build_system_prompt(self) -> str:
        parts = [self.system_prompt.strip()]
        if self.style.strip():
            parts.append(f"说话风格：{self.style.strip()}")
        if self.boundaries.topics:
            blocked = "、".join(self.boundaries.topics)
            parts.append(f"请回避这些话题：{blocked}")
        parts.append(
            "若用户说「记住：xxx」，把 xxx 当作需要长期保留的事实确认下来；"
            "若用户说「忘掉：xxx」，表示不再需要相关记忆。"
        )
        return "\n\n".join(parts)


DEFAULT_CHARACTER = CharacterPack(
    id="assistant-default",
    name="默认助手",
    description="AgentTest 内置工作向助手",
    system_prompt=(
        "你是 AgentTest 的默认助手。回答简洁、可执行，优先使用中文。"
        "当你需要查看或修改沙箱工作区文件时，主动调用桌面工具。"
    ),
    style="简洁、务实、少客套",
    greeting="你好，我是 AgentTest 默认助手。可以聊天，也可以帮你读写工作区文件。",
    boundaries=Boundaries(tools="full"),
    voice=VoiceConfig(),
)


def _candidate_dirs(characters_dir: Path) -> list[Path]:
    dirs: list[Path] = []
    if characters_dir.exists():
        for child in sorted(characters_dir.iterdir()):
            if child.is_dir() and child.name != "_examples":
                dirs.append(child)
        examples = characters_dir / "_examples"
        if examples.exists():
            for child in sorted(examples.iterdir()):
                if child.is_dir():
                    dirs.append(child)
    return dirs


def load_character_pack(folder: Path) -> CharacterPack | None:
    yaml_path = folder / "character.yaml"
    if not yaml_path.exists():
        return None
    raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if "id" not in raw:
        raw["id"] = folder.name
    pack = CharacterPack.model_validate(raw)
    pack.path = str(folder)
    return pack


class PersonaService:
    def __init__(self, characters_dir: Path | None = None) -> None:
        settings = get_settings()
        self.characters_dir = characters_dir or Path(settings.characters_dir)

    def list_packs(self) -> list[CharacterPack]:
        packs: list[CharacterPack] = []
        seen: set[str] = set()
        for folder in _candidate_dirs(self.characters_dir):
            pack = load_character_pack(folder)
            if not pack or pack.id in seen:
                continue
            seen.add(pack.id)
            packs.append(pack)
        if "assistant-default" not in seen:
            packs.insert(0, DEFAULT_CHARACTER)
        return packs

    def get_pack(self, persona_id: str | None) -> CharacterPack:
        if not persona_id:
            return DEFAULT_CHARACTER
        for pack in self.list_packs():
            if pack.id == persona_id:
                return pack
        return DEFAULT_CHARACTER
