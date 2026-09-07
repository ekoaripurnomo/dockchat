"""Docker orchestration via the Docker SDK for Python.

Container names are namespaced per-user (``dockchat_<user>_<name>``) to provide
basic isolation. If the Docker daemon is unreachable, operations raise a clear
HTTP error rather than crashing the app.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException

from backend.config import Settings
from backend.models.docker import ContainerInfo, CreateContainerRequest


class DockerService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._available = False

    def connect(self) -> None:
        try:
            import docker

            if self.settings.docker_host:
                self._client = docker.DockerClient(base_url=self.settings.docker_host)
            else:
                self._client = docker.from_env()
            self._client.ping()
            self._available = True
        except Exception:
            self._client = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def _require(self):
        if not self._available or self._client is None:
            raise HTTPException(status_code=503, detail="Docker daemon is not available")
        return self._client

    def _namespace(self, user_id: UUID, name: Optional[str]) -> str:
        short = str(user_id).split("-")[0]
        base = name or "container"
        return f"dockchat_{short}_{base}"

    def _label(self, user_id: UUID) -> Dict[str, str]:
        return {"dockchat.user": str(user_id)}

    async def create_container(
        self, request: CreateContainerRequest, user_id: UUID
    ) -> ContainerInfo:
        client = self._require()
        name = self._namespace(user_id, request.name)
        ports = {f"{cp}/tcp": hp for cp, hp in request.ports.items()}
        volumes = {
            host: {"bind": container, "mode": "rw"}
            for host, container in request.volumes.items()
        }

        def _run():
            return client.containers.run(
                image=request.image, name=name, detach=request.detach,
                ports=ports or None, environment=request.environment or None,
                volumes=volumes or None, command=request.command,
                labels=self._label(user_id),
            )

        try:
            container = await asyncio.to_thread(_run)
        except Exception as exc:  # docker.errors.*
            raise HTTPException(status_code=400, detail=f"Failed to create container: {exc}")
        return self._to_info(container)

    async def list_containers(self, user_id: UUID) -> List[ContainerInfo]:
        client = self._require()

        def _list():
            return client.containers.list(
                all=True, filters={"label": f"dockchat.user={user_id}"}
            )

        containers = await asyncio.to_thread(_list)
        return [self._to_info(c) for c in containers]

    async def container_action(self, user_id: UUID, container_id: str, action: str) -> ContainerInfo:
        client = self._require()

        def _act():
            container = client.containers.get(container_id)
            if container.labels.get("dockchat.user") != str(user_id):
                raise PermissionError("Container does not belong to user")
            if action == "start":
                container.start()
            elif action == "stop":
                container.stop()
            elif action == "restart":
                container.restart()
            elif action == "remove":
                container.remove(force=True)
                return None
            else:
                raise ValueError(f"Unknown action: {action}")
            container.reload()
            return container

        try:
            container = await asyncio.to_thread(_act)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Action failed: {exc}")

        if container is None:
            return ContainerInfo(id=container_id, name="", image="", status="removed")
        return self._to_info(container)

    def _to_info(self, container: Any) -> ContainerInfo:
        image = ""
        try:
            image = container.image.tags[0] if container.image.tags else container.image.short_id
        except Exception:
            image = str(getattr(container, "image", ""))
        return ContainerInfo(
            id=container.short_id,
            name=container.name,
            image=image,
            status=container.status,
            ports=getattr(container, "ports", {}) or {},
        )
