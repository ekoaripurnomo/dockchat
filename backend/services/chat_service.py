"""Chat orchestration: connects the selected LLM provider to Docker tools.

Uses OpenAI-compatible tool calling for vLLM/OpenAI providers. Anthropic uses
its own tool schema. When a tool is requested by the model, it is executed
against the Docker/Project services and the result is fed back for a final
natural-language answer.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.models.docker import (
    BuildImageRequest,
    CreateContainerRequest,
    DeployProjectRequest,
    DockerfileGenerationRequest,
    ProjectAnalysisRequest,
)
from backend.models.providers import ProviderType
from backend.services.ai_provider_manager import AIProviderManager
from backend.services.docker_service import DockerService
from backend.services.project_service import ProjectService

SYSTEM_PROMPT = (
    "You are dockchat, an AI assistant that manages Docker containers and generates "
    "Docker configurations through conversation. Use the provided tools to do the work "
    "yourself; never tell the user to run docker commands manually.\n"
    "Rules:\n"
    "- To run a project as a container, use deploy_project (it analyzes, writes the "
    "Dockerfile, builds the image, and runs the container in one step). Prefer this "
    "when the user asks to build and/or run a project directory.\n"
    "- create_container only works with an image that already exists. If the image "
    "was not built yet, use build_image or deploy_project first. Do not invent image names.\n"
    "- ports must be a JSON object mapping container port to host port using STRING keys, "
    'e.g. {"80": 8080}. dockchat auto-selects a free host port if the requested one is taken.\n'
    "- Be concise and confirm the concrete actions you took (image tag, container name, port)."
)

# OpenAI-compatible tool schema.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_project",
            "description": "Analyze a project directory to detect its type, language and suggested base image.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Absolute path to the project directory"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_dockerfile",
            "description": "Generate a Dockerfile for a project directory. Optionally write it to disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "base_image": {"type": "string"},
                    "exposed_port": {"type": "integer"},
                    "write_to_disk": {"type": "boolean"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_image",
            "description": "Build a Docker image from a project directory that already contains a Dockerfile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the project directory"},
                    "tag": {"type": "string", "description": "Image tag, e.g. myapp:latest"},
                },
                "required": ["path", "tag"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_project",
            "description": (
                "One-shot deploy: analyze a project directory, generate and write its "
                "Dockerfile, build the image, and run it as a container. Use this when the "
                "user asks to build and run / deploy a project."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the project directory"},
                    "name": {"type": "string", "description": "Optional container name"},
                    "base_image": {"type": "string"},
                    "exposed_port": {"type": "integer", "description": "Container port to publish"},
                    "host_port": {"type": "integer", "description": "Host port (defaults to a free port)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_containers",
            "description": "List the current user's Docker containers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_container",
            "description": (
                "Create and run a container from an image that ALREADY EXISTS locally. "
                "If the image was not built yet, call build_image or deploy_project first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image": {"type": "string"},
                    "name": {"type": "string"},
                    "ports": {
                        "type": "object",
                        "description": 'Map of container_port -> host_port with string keys, e.g. {"80": 8080}',
                    },
                    "environment": {"type": "object"},
                },
                "required": ["image"],
            },
        },
    },
]


class ChatService:
    def __init__(
        self,
        provider_manager: AIProviderManager,
        docker_service: DockerService,
        project_service: ProjectService,
    ):
        self.providers = provider_manager
        self.docker = docker_service
        self.projects = project_service

    # Matches absolute unix paths like /home/eko/data/hextris in a message.
    _PATH_RE = re.compile(r"(/[\w.\-]+(?:/[\w.\-]+)+)")

    def _auto_analysis_context(self, message: str) -> Optional[str]:
        """When tool-calling is unavailable, proactively analyze any project path
        mentioned in the message and return a context string for the model.

        This lets the assistant answer with real project details (type, language,
        framework, files, README excerpt) instead of asking the user for them.
        """
        match = self._PATH_RE.search(message)
        if not match:
            return None
        path = match.group(1).rstrip("/.,)")
        if not self.projects.validate_user_path(path):
            return None
        try:
            analysis = self.projects.analyze_project(ProjectAnalysisRequest(path=path))
        except Exception:
            return None
        data = analysis.model_dump()
        # Keep the injected context compact.
        for key in ("detected_files",):
            if isinstance(data.get(key), list) and len(data[key]) > 40:
                data[key] = data[key][:40] + ["..."]
        return (
            "The following project analysis was performed automatically on the path "
            f"mentioned by the user. Use it to answer without asking for more details:\n"
            f"{json.dumps(data, indent=2, default=str)}"
        )

    @staticmethod
    def _normalize_ports(args: Dict[str, Any]) -> None:
        """Coerce ports into {str: int}. Models sometimes emit integer keys
        ({80: 80}) or string values, which would fail validation."""
        ports = args.get("ports")
        if isinstance(ports, dict):
            args["ports"] = {str(k): int(v) for k, v in ports.items()}

    async def _dispatch_tool(self, name: str, args: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        try:
            if name == "analyze_project":
                return self.projects.analyze_project(ProjectAnalysisRequest(**args)).model_dump()
            if name == "generate_dockerfile":
                return self.projects.generate_dockerfile(DockerfileGenerationRequest(**args)).model_dump()
            if name == "build_image":
                return (await self.docker.build_image(
                    args["path"], args["tag"], user_id
                )).model_dump()
            if name == "deploy_project":
                return (await self.projects.deploy_project(
                    DeployProjectRequest(**args), user_id, self.docker
                )).model_dump()
            if name == "list_containers":
                items = await self.docker.list_containers(user_id)
                return {"containers": [c.model_dump() for c in items]}
            if name == "create_container":
                self._normalize_ports(args)
                info = await self.docker.create_container(CreateContainerRequest(**args), user_id)
                return info.model_dump()
            return {"error": f"Unknown tool: {name}"}
        except Exception as exc:  # surface tool errors to the model
            return {"error": str(exc)}

    async def chat(
        self, user_id: UUID, message: str, history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        client, config = await self.providers.get_client(user_id=str(user_id))
        if config.provider_type == ProviderType.ANTHROPIC:
            return await self._chat_anthropic(client, config, user_id, message, history or [])
        return await self._chat_openai(client, config, user_id, message, history or [])

    async def _chat_openai(self, client, config, user_id, message, history) -> Dict[str, Any]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        tool_calls_made: List[Dict[str, Any]] = []
        use_tools = getattr(config, "supports_tools", True)

        # Without server-side tool-calling, gather project context ourselves so
        # the model can answer instead of asking the user for details.
        if not use_tools:
            ctx = self._auto_analysis_context(message)
            if ctx:
                messages.append({"role": "system", "content": ctx})
                tool_calls_made.append({"tool": "analyze_project", "auto": True})

        messages.append({"role": "user", "content": message})

        for _ in range(5):  # bounded tool-call loop
            kwargs = dict(
                model=config.model, messages=messages,
                temperature=config.temperature, max_tokens=config.max_tokens, top_p=config.top_p,
            )
            if use_tools:
                kwargs["tools"] = TOOLS
            try:
                resp = await client.chat.completions.create(**kwargs)
            except Exception as exc:
                # Some servers (e.g. vLLM without --enable-auto-tool-choice)
                # reject requests that include tools. Retry once without them
                # so the user still gets a conversational reply.
                if use_tools and "tool" in str(exc).lower():
                    use_tools = False
                    kwargs.pop("tools", None)
                    resp = await client.chat.completions.create(**kwargs)
                else:
                    raise

            choice = resp.choices[0].message
            if not use_tools or not choice.tool_calls:
                return {"reply": choice.content or "", "tool_calls": tool_calls_made}

            messages.append({
                "role": "assistant", "content": choice.content,
                "tool_calls": [tc.model_dump() for tc in choice.tool_calls],
            })
            for tc in choice.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = await self._dispatch_tool(tc.function.name, args, user_id)
                tool_calls_made.append({"tool": tc.function.name, "args": args, "result": result})
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

        return {"reply": "Reached tool-call limit. Please refine your request.", "tool_calls": tool_calls_made}

    async def _chat_anthropic(self, client, config, user_id, message, history) -> Dict[str, Any]:
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            }
            for t in TOOLS
        ]
        messages = list(history)
        tool_calls_made: List[Dict[str, Any]] = []
        if not getattr(config, "supports_tools", True):
            ctx = self._auto_analysis_context(message)
            if ctx:
                messages.append({"role": "user", "content": ctx})
                tool_calls_made.append({"tool": "analyze_project", "auto": True})
        messages.append({"role": "user", "content": message})

        for _ in range(5):
            resp = await client.messages.create(
                model=config.model, system=SYSTEM_PROMPT, messages=messages,
                tools=anthropic_tools, max_tokens=config.max_tokens, temperature=config.temperature,
            )
            tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
            if not tool_uses:
                text = "".join(getattr(b, "text", "") for b in resp.content)
                return {"reply": text, "tool_calls": tool_calls_made}

            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for tu in tool_uses:
                result = await self._dispatch_tool(tu.name, tu.input, user_id)
                tool_calls_made.append({"tool": tu.name, "args": tu.input, "result": result})
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id,
                    "content": json.dumps(result, default=str),
                })
            messages.append({"role": "user", "content": tool_results})

        return {"reply": "Reached tool-call limit. Please refine your request.", "tool_calls": tool_calls_made}
