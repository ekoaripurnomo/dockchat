"""AI provider configuration routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user, get_provider_manager
from backend.models.providers import ProviderParameters, ProviderSwitchRequest
from backend.services.ai_provider_manager import AIProviderManager

router = APIRouter(prefix="/api/config", tags=["configuration"])


@router.get("/providers")
async def list_providers(
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: AIProviderManager = Depends(get_provider_manager),
):
    return manager.list_providers(str(current_user["user_id"]))


@router.get("/providers/current")
async def current_provider(
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: AIProviderManager = Depends(get_provider_manager),
):
    active = manager.get_active_provider(str(current_user["user_id"]))
    if not active:
        raise HTTPException(status_code=404, detail="No active provider")
    return active


@router.post("/providers/switch")
async def switch_provider(
    body: ProviderSwitchRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: AIProviderManager = Depends(get_provider_manager),
):
    ok = await manager.switch_provider(body.provider_name, str(current_user["user_id"]))
    if not ok:
        raise HTTPException(status_code=400, detail="Unable to switch provider")
    return {"message": f"Switched to {body.provider_name}"}


@router.get("/providers/{name}/test")
async def test_provider(
    name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: AIProviderManager = Depends(get_provider_manager),
):
    connected = await manager.test_connection(name, str(current_user["user_id"]))
    return {"connected": connected}


@router.put("/providers/{name}/parameters")
async def update_parameters(
    name: str,
    params: ProviderParameters,
    current_user: Dict[str, Any] = Depends(get_current_user),
    manager: AIProviderManager = Depends(get_provider_manager),
):
    ok = manager.update_parameters(
        name, params.model_dump(exclude_none=True), str(current_user["user_id"])
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"message": "Parameters updated"}
