"""Docker and project management routes (authenticated)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.dependencies import (
    get_admin_user,
    get_audit_service,
    get_current_user,
    get_docker_service,
    get_project_service,
)
from backend.models.docker import (
    BuildImageRequest,
    CreateContainerRequest,
    DeployProjectRequest,
    DockerfileGenerationRequest,
    ProjectAnalysisRequest,
)
from backend.services.audit_service import AuditService
from backend.services.docker_service import DockerService
from backend.services.project_service import ProjectService

router = APIRouter(prefix="/api/docker", tags=["docker"])


@router.get("/status")
async def docker_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service),
):
    return {"available": docker_service.available}


@router.post("/containers")
async def create_container(
    request: CreateContainerRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service),
    audit: AuditService = Depends(get_audit_service),
):
    container = await docker_service.create_container(request, current_user["user_id"])
    await audit.log_action(
        current_user["user_id"], "create_container", "container", container.id, request.model_dump()
    )
    return container


@router.get("/containers")
async def list_containers(
    current_user: Dict[str, Any] = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service),
):
    return await docker_service.list_containers(current_user["user_id"])


@router.get("/containers/all")
async def list_all_containers(
    admin_user: Dict[str, Any] = Depends(get_admin_user),
    docker_service: DockerService = Depends(get_docker_service),
):
    """List all containers on the host (admin/superuser only)."""
    return await docker_service.list_all_containers()


@router.post("/containers/{container_id}/{action}")
async def container_action(
    container_id: str,
    action: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service),
    audit: AuditService = Depends(get_audit_service),
):
    result = await docker_service.container_action(current_user["user_id"], container_id, action)
    await audit.log_action(current_user["user_id"], f"container_{action}", "container", container_id)
    return result


@router.get("/images")
async def list_images(
    current_user: Dict[str, Any] = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service),
):
    return await docker_service.list_images(current_user["user_id"])


@router.post("/images/build")
async def build_image(
    request: BuildImageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service),
    project_service: ProjectService = Depends(get_project_service),
    audit: AuditService = Depends(get_audit_service),
):
    # Reuse the project service's path validation for the build context.
    if not project_service.validate_user_path(request.path):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied to this path")
    result = await docker_service.build_image(
        request.path, request.tag, current_user["user_id"], request.dockerfile
    )
    await audit.log_action(current_user["user_id"], "build_image", "image", request.tag)
    return result


@router.post("/projects/deploy")
async def deploy_project(
    request: DeployProjectRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service),
    project_service: ProjectService = Depends(get_project_service),
    audit: AuditService = Depends(get_audit_service),
):
    """Analyze a project, generate its Dockerfile, build the image and run it."""
    result = await project_service.deploy_project(
        request, current_user["user_id"], docker_service
    )
    await audit.log_action(
        current_user["user_id"], "deploy_project", "container",
        result.container.id, {"path": request.path, "image": result.image.tags},
    )
    return result


@router.post("/projects/analyze")
async def analyze_project(
    request: ProjectAnalysisRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
):
    return project_service.analyze_project(request)


@router.post("/projects/generate-dockerfile")
async def generate_dockerfile(
    request: DockerfileGenerationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    audit: AuditService = Depends(get_audit_service),
):
    result = project_service.generate_dockerfile(request)
    await audit.log_action(
        current_user["user_id"], "generate_dockerfile", "project", request.path
    )
    return result
