"""Docker and project related request/response models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateContainerRequest(BaseModel):
    image: str
    name: Optional[str] = None
    ports: Dict[str, int] = Field(default_factory=dict)   # container_port -> host_port
    environment: Dict[str, str] = Field(default_factory=dict)
    volumes: Dict[str, str] = Field(default_factory=dict)  # host_path -> container_path
    command: Optional[str] = None
    detach: bool = True


class ContainerInfo(BaseModel):
    id: str
    name: str
    image: str
    status: str
    ports: Dict[str, Any] = Field(default_factory=dict)


class ProjectAnalysisRequest(BaseModel):
    path: str


class ProjectAnalysis(BaseModel):
    path: str
    project_type: str
    language: Optional[str] = None
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    entrypoint: Optional[str] = None
    detected_files: List[str] = Field(default_factory=list)
    subdirectories: List[str] = Field(default_factory=list)
    suggested_base_image: Optional[str] = None
    exposed_port: Optional[int] = None
    readme_excerpt: Optional[str] = None
    summary: Optional[str] = None


class DockerfileGenerationRequest(BaseModel):
    path: str
    base_image: Optional[str] = None
    exposed_port: Optional[int] = None
    write_to_disk: bool = False


class DockerfileResponse(BaseModel):
    dockerfile: str
    dockerignore: str
    written_path: Optional[str] = None


class BuildImageRequest(BaseModel):
    path: str                       # build context (project directory)
    tag: str                        # image tag, e.g. "myapp:latest"
    dockerfile: str = "Dockerfile"  # Dockerfile name relative to the context


class ImageInfo(BaseModel):
    id: str
    tags: List[str] = Field(default_factory=list)
    size: Optional[int] = None


class BuildImageResponse(BaseModel):
    image: ImageInfo
    logs: List[str] = Field(default_factory=list)


class DeployProjectRequest(BaseModel):
    """One-shot: analyze -> generate Dockerfile -> build image -> run container."""
    path: str
    tag: Optional[str] = None            # defaults to <dirname>:latest
    name: Optional[str] = None           # container name
    base_image: Optional[str] = None
    exposed_port: Optional[int] = None   # container port to publish
    host_port: Optional[int] = None      # host port (defaults to exposed_port)
    environment: Dict[str, str] = Field(default_factory=dict)


class DeployProjectResponse(BaseModel):
    analysis: ProjectAnalysis
    dockerfile: str
    image: ImageInfo
    container: ContainerInfo
    build_logs: List[str] = Field(default_factory=list)
