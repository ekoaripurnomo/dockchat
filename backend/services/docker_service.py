"""Docker orchestration via the Docker SDK for Python.

Container names are namespaced per-user (``dockchat_<user>_<name>``) to provide
basic isolation. If the Docker daemon is unreachable, operations raise a clear
HTTP error rather than crashing the app.
"""
from __future__ import annotations

import asyncio
import socket
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException

from backend.config import Settings
from backend.models.docker import (
    BuildImageResponse,
    ContainerInfo,
    CreateContainerRequest,
    ImageInfo,
)


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

    @staticmethod
    def _port_in_use(port: int) -> bool:
        """Return True if a host TCP port is already bound."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return False
            except OSError:
                return True

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("0.0.0.0", 0))
            return sock.getsockname()[1]

    def _image_exists(self, tag: str) -> bool:
        try:
            self._client.images.get(tag)
            return True
        except Exception:
            return False

    async def create_container(
        self, request: CreateContainerRequest, user_id: UUID, auto_port: bool = True
    ) -> ContainerInfo:
        client = self._require()

        # Fail early with a clear message if the image isn't available locally,
        # rather than a cryptic pull/registry error.
        if not await asyncio.to_thread(self._image_exists, request.image):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Image '{request.image}' not found locally. Build it first "
                    f"(build_image / deploy_project) or use a valid image name."
                ),
            )

        name = self._namespace(user_id, request.name)

        # Resolve host port conflicts. ports maps container_port -> host_port.
        resolved_ports: Dict[str, int] = {}
        remapped: Dict[str, int] = {}
        for cp, hp in request.ports.items():
            hp = int(hp)
            if self._port_in_use(hp):
                if auto_port:
                    new_hp = self._find_free_port()
                    remapped[str(hp)] = new_hp
                    hp = new_hp
                else:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Host port {hp} is already in use. Choose another port.",
                    )
            resolved_ports[f"{cp}/tcp"] = hp

        volumes = {
            host: {"bind": container, "mode": "rw"}
            for host, container in request.volumes.items()
        }

        def _run():
            return client.containers.run(
                image=request.image, name=name, detach=request.detach,
                ports=resolved_ports or None, environment=request.environment or None,
                volumes=volumes or None, command=request.command,
                labels=self._label(user_id),
            )

        try:
            container = await asyncio.to_thread(_run)
        except Exception as exc:  # docker.errors.*
            raise HTTPException(status_code=400, detail=f"Failed to create container: {exc}")
        info = self._to_info(container)
        if remapped:
            info.ports = {**info.ports, "_remapped_from": remapped}
        return info

    async def build_image(
        self, context_path: str, tag: str, user_id: UUID, dockerfile: str = "Dockerfile"
    ) -> BuildImageResponse:
        """Build a Docker image from a project directory (build context).

        The low-level API is used so build output can be streamed back to the
        caller. The resulting image is labeled with the owning user.
        """
        client = self._require()

        def _build():
            logs: List[str] = []
            api = client.api  # low-level client for streaming build logs
            stream = api.build(
                path=context_path, dockerfile=dockerfile, tag=tag, rm=True,
                labels={"dockchat.user": str(user_id)}, decode=True,
            )
            image_id = None
            for chunk in stream:
                if "stream" in chunk:
                    line = chunk["stream"].strip()
                    if line:
                        logs.append(line)
                elif "error" in chunk:
                    raise RuntimeError(chunk["error"])
                elif "aux" in chunk and "ID" in chunk["aux"]:
                    image_id = chunk["aux"]["ID"]
            image = client.images.get(image_id or tag)
            return image, logs

        try:
            image, logs = await asyncio.to_thread(_build)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Image build failed: {exc}")
        return BuildImageResponse(image=self._image_info(image), logs=logs)

    async def list_images(self, user_id: UUID) -> List[ImageInfo]:
        client = self._require()

        def _list():
            return client.images.list(filters={"label": f"dockchat.user={user_id}"})

        images = await asyncio.to_thread(_list)
        return [self._image_info(img) for img in images]

    async def list_containers(self, user_id: UUID) -> List[ContainerInfo]:
        client = self._require()

        def _list():
            return client.containers.list(
                all=True, filters={"label": f"dockchat.user={user_id}"}
            )

        containers = await asyncio.to_thread(_list)
        return [self._to_info(c) for c in containers]

    async def list_all_containers(self) -> List[ContainerInfo]:
        """List every container on the host (admin only).

        Unlike list_containers, this is not filtered by the dockchat.user label,
        so it includes containers created outside the app.
        """
        client = self._require()

        def _list():
            return client.containers.list(all=True)

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

    def _image_info(self, image: Any) -> ImageInfo:
        return ImageInfo(
            id=image.short_id,
            tags=list(getattr(image, "tags", []) or []),
            size=(image.attrs or {}).get("Size"),
        )

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
