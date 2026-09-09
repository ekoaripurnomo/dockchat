"""Project analysis and Dockerfile generation.

Detects the project type from files on disk and generates a production-ready
Dockerfile + .dockerignore using Jinja2 templates. Path access is restricted to
the configured ALLOWED_PATHS to prevent arbitrary filesystem reads.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException
from jinja2 import Environment, StrictUndefined

from uuid import UUID

from backend.config import Settings
from backend.models.docker import (
    CreateContainerRequest,
    DeployProjectRequest,
    DeployProjectResponse,
    DockerfileGenerationRequest,
    DockerfileResponse,
    ProjectAnalysis,
    ProjectAnalysisRequest,
)

# Ordered detection rules: first match wins.
_DETECTORS = [
    {
        "type": "node", "marker": "package.json", "language": "javascript",
        "package_manager": "npm", "base_image": "node:20-alpine", "port": 3000,
    },
    {
        "type": "python", "marker": "requirements.txt", "language": "python",
        "package_manager": "pip", "base_image": "python:3.11-slim", "port": 8000,
    },
    {
        "type": "python", "marker": "pyproject.toml", "language": "python",
        "package_manager": "pip", "base_image": "python:3.11-slim", "port": 8000,
    },
    {
        "type": "go", "marker": "go.mod", "language": "go",
        "package_manager": "go", "base_image": "golang:1.22-alpine", "port": 8080,
    },
    {
        "type": "rust", "marker": "Cargo.toml", "language": "rust",
        "package_manager": "cargo", "base_image": "rust:1.77-slim", "port": 8080,
    },
    {
        "type": "java", "marker": "pom.xml", "language": "java",
        "package_manager": "maven", "base_image": "eclipse-temurin:21-jdk", "port": 8080,
    },
    {
        "type": "php", "marker": "composer.json", "language": "php",
        "package_manager": "composer", "base_image": "php:8.3-apache", "port": 80,
    },
    {
        "type": "ruby", "marker": "Gemfile", "language": "ruby",
        "package_manager": "bundler", "base_image": "ruby:3.3-slim", "port": 3000,
    },
]

_DOCKERFILE_TEMPLATES = {
    "node": """\
FROM {{ base_image }}
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY . .
EXPOSE {{ port }}
CMD ["node", "{{ entrypoint }}"]
""",
    "python": """\
FROM {{ base_image }}
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {{ port }}
CMD ["python", "{{ entrypoint }}"]
""",
    "go": """\
FROM {{ base_image }} AS build
WORKDIR /src
COPY go.* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /app/server ./...
FROM gcr.io/distroless/static
COPY --from=build /app/server /server
EXPOSE {{ port }}
ENTRYPOINT ["/server"]
""",
    "rust": """\
FROM {{ base_image }} AS build
WORKDIR /src
COPY . .
RUN cargo build --release
FROM debian:bookworm-slim
COPY --from=build /src/target/release/* /usr/local/bin/app
EXPOSE {{ port }}
CMD ["app"]
""",
    "java": """\
FROM {{ base_image }} AS build
WORKDIR /src
COPY . .
RUN ./mvnw -q package -DskipTests || mvn -q package -DskipTests
FROM eclipse-temurin:21-jre
COPY --from=build /src/target/*.jar /app/app.jar
EXPOSE {{ port }}
CMD ["java", "-jar", "/app/app.jar"]
""",
    "static": """\
FROM {{ base_image }}
COPY . /usr/share/nginx/html
EXPOSE {{ port }}
CMD ["nginx", "-g", "daemon off;"]
""",
    "php": """\
FROM {{ base_image }}
WORKDIR /var/www/html
COPY . .
EXPOSE {{ port }}
""",
    "ruby": """\
FROM {{ base_image }}
WORKDIR /app
COPY Gemfile* ./
RUN bundle install
COPY . .
EXPOSE {{ port }}
CMD ["ruby", "{{ entrypoint }}"]
""",
    "generic": """\
FROM {{ base_image }}
WORKDIR /app
COPY . .
EXPOSE {{ port }}
CMD ["/bin/sh"]
""",
}

_DOCKERIGNORE = """\
.git
node_modules
__pycache__
*.pyc
.env
target
dist
build
.venv
venv
"""


class ProjectService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._jinja = Environment(undefined=StrictUndefined, keep_trailing_newline=True)

    def _validate_path(self, path: str) -> Path:
        resolved = Path(path).expanduser().resolve()
        allowed = [Path(p).expanduser().resolve() for p in self.settings.allowed_paths_list]
        if not any(resolved == a or a in resolved.parents for a in allowed):
            raise HTTPException(status_code=403, detail="Access denied to this path")
        if not resolved.exists() or not resolved.is_dir():
            raise HTTPException(status_code=404, detail="Directory not found")
        return resolved

    def validate_user_path(self, path: str) -> bool:
        try:
            self._validate_path(path)
            return True
        except HTTPException:
            return False

    def analyze_project(self, request: ProjectAnalysisRequest) -> ProjectAnalysis:
        root = self._validate_path(request.path)
        present = {p.name for p in root.iterdir() if p.is_file()}
        subdirs = sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
        readme = self._read_readme(root, present)

        for rule in _DETECTORS:
            if rule["marker"] in present:
                entrypoint = self._guess_entrypoint(root, rule["type"], present)
                framework = self._guess_framework(root, rule["type"], present)
                analysis = ProjectAnalysis(
                    path=str(root),
                    project_type=rule["type"],
                    language=rule["language"],
                    framework=framework,
                    package_manager=rule["package_manager"],
                    entrypoint=entrypoint,
                    detected_files=sorted(present),
                    subdirectories=subdirs,
                    suggested_base_image=rule["base_image"],
                    exposed_port=rule["port"],
                    readme_excerpt=readme,
                )
                analysis.summary = self._summarize(analysis)
                return analysis

        # No build-system marker. Detect a static website (HTML/JS/CSS).
        if self._is_static_site(present, subdirs):
            analysis = ProjectAnalysis(
                path=str(root), project_type="static", language="html",
                framework="static-site", entrypoint="index.html",
                detected_files=sorted(present), subdirectories=subdirs,
                suggested_base_image="nginx:alpine", exposed_port=80,
                readme_excerpt=readme,
            )
            analysis.summary = self._summarize(analysis)
            return analysis

        analysis = ProjectAnalysis(
            path=str(root), project_type="generic", detected_files=sorted(present),
            subdirectories=subdirs, suggested_base_image="ubuntu:22.04",
            exposed_port=8080, readme_excerpt=readme,
        )
        analysis.summary = self._summarize(analysis)
        return analysis

    def _is_static_site(self, present: set, subdirs: List[str]) -> bool:
        html_files = [f for f in present if f.lower().endswith((".html", ".htm"))]
        has_index = any(f.lower() == "index.html" for f in present)
        has_web_assets = bool({"js", "css", "style", "styles", "assets", "static"} & set(subdirs))
        return has_index or (bool(html_files) and has_web_assets)

    def _read_readme(self, root: Path, present: set) -> Optional[str]:
        for name in present:
            if name.lower() in ("readme.md", "readme.txt", "readme", "readme.rst"):
                try:
                    text = (root / name).read_text(encoding="utf-8", errors="ignore")
                    return text[:1500]
                except OSError:
                    return None
        return None

    def _summarize(self, a: ProjectAnalysis) -> str:
        parts = [f"Detected a {a.project_type} project"]
        if a.framework:
            parts.append(f"using {a.framework}")
        if a.language:
            parts.append(f"({a.language})")
        parts.append(f". Suggested base image: {a.suggested_base_image}, port {a.exposed_port}.")
        if a.entrypoint:
            parts.append(f" Entry point: {a.entrypoint}.")
        return " ".join(parts).replace(" .", ".")

    def _guess_entrypoint(self, root: Path, ptype: str, present: set) -> Optional[str]:
        if ptype == "node":
            for candidate in ("server.js", "index.js", "app.js", "src/index.js"):
                if (root / candidate).exists():
                    return candidate
            return "index.js"
        if ptype == "python":
            for candidate in ("main.py", "app.py", "wsgi.py", "manage.py"):
                if candidate in present:
                    return candidate
            return "main.py"
        return None

    def _guess_framework(self, root: Path, ptype: str, present: set) -> Optional[str]:
        try:
            if ptype == "node" and "package.json" in present:
                content = (root / "package.json").read_text(encoding="utf-8", errors="ignore")
                for fw in ("next", "express", "react", "vue", "nestjs"):
                    if fw in content:
                        return fw
            if ptype == "python" and "requirements.txt" in present:
                content = (root / "requirements.txt").read_text(encoding="utf-8", errors="ignore").lower()
                for fw in ("fastapi", "flask", "django"):
                    if fw in content:
                        return fw
        except OSError:
            return None
        return None

    def generate_dockerfile(self, request: DockerfileGenerationRequest) -> DockerfileResponse:
        analysis = self.analyze_project(ProjectAnalysisRequest(path=request.path))
        template_str = _DOCKERFILE_TEMPLATES.get(analysis.project_type, _DOCKERFILE_TEMPLATES["generic"])
        template = self._jinja.from_string(template_str)
        dockerfile = template.render(
            base_image=request.base_image or analysis.suggested_base_image or "ubuntu:22.04",
            port=request.exposed_port or analysis.exposed_port or 8080,
            entrypoint=analysis.entrypoint or "app",
        )

        written_path = None
        if request.write_to_disk:
            root = self._validate_path(request.path)
            dockerfile_path = root / "Dockerfile"
            dockerfile_path.write_text(dockerfile, encoding="utf-8")
            (root / ".dockerignore").write_text(_DOCKERIGNORE, encoding="utf-8")
            written_path = str(dockerfile_path)

        return DockerfileResponse(
            dockerfile=dockerfile, dockerignore=_DOCKERIGNORE, written_path=written_path
        )

    async def deploy_project(
        self, request: DeployProjectRequest, user_id: UUID, docker_service
    ) -> DeployProjectResponse:
        """End-to-end: analyze -> generate Dockerfile (on disk) -> build -> run.

        ``docker_service`` is passed in to avoid a construction-time circular
        dependency between the project and docker services.
        """
        root = self._validate_path(request.path)

        analysis = self.analyze_project(ProjectAnalysisRequest(path=str(root)))
        container_port = request.exposed_port or analysis.exposed_port or 8080

        # 1. Generate and write the Dockerfile + .dockerignore.
        df = self.generate_dockerfile(DockerfileGenerationRequest(
            path=str(root), base_image=request.base_image,
            exposed_port=container_port, write_to_disk=True,
        ))

        # 2. Build the image.
        tag = request.tag or f"{root.name.lower()}:latest"
        build = await docker_service.build_image(str(root), tag, user_id)

        # 3. Run the container, publishing the exposed port.
        host_port = request.host_port or container_port
        container = await docker_service.create_container(
            CreateContainerRequest(
                image=tag, name=request.name or root.name.lower(),
                ports={str(container_port): host_port},
                environment=request.environment,
            ),
            user_id,
        )

        return DeployProjectResponse(
            analysis=analysis, dockerfile=df.dockerfile,
            image=build.image, container=container, build_logs=build.logs,
        )
