from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.desktop import DesktopError, DesktopService

router = APIRouter(prefix="/desktop", tags=["desktop"])


class WriteFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    content: str = Field(default="", max_length=500_000)
    overwrite: bool = True


@router.get("/info")
def desktop_info() -> dict[str, Any]:
    return DesktopService().info()


@router.get("/ls")
def list_directory(path: str = ".") -> dict[str, Any]:
    try:
        items = DesktopService().list_dir(path)
    except DesktopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": path, "items": items}


@router.get("/read")
def read_file(path: str) -> dict[str, Any]:
    try:
        return DesktopService().read_file(path)
    except DesktopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/write")
def write_file(body: WriteFileRequest) -> dict[str, Any]:
    try:
        return DesktopService().write_file(body.path, body.content, body.overwrite)
    except DesktopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
