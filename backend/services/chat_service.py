"""Chat orchestration: connects the selected LLM provider to Docker tools.

Uses OpenAI-compatible tool calling for vLLM/OpenAI providers. Anthropic uses
its own tool schema. When a tool is requested by the model, it is executed
against the Docker/Project services and the result is fed back for a final
natural-language answer.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.models.docker import (
    CreateContainerRequest,
    DockerfileGenerationRequest,
    ProjectAnalysisRequest,
)
from backend.models.providers import ProviderType
from backend.services.ai_provider_manager import AIProviderManager
from backend.services.docker_service import DockerService
from backend.services.project_service import ProjectService

SYSTEM_PROMPT = (
    "You are dockchat, an AI assistant that manages Docker containers and generates "
    "Docker configurations through conversation. Use the provided tools to inspect "
    "projects, generate Dockerfiles, and manage containers on the user's behalf. "
    "Be concise and confirm actions you take."
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
            "name": "list_containers",
            "description": "List the current user's Docker containers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_container",
            "description": "Create and run a Docker container from an image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image": {"type": "string"},
                    "name": {"type": "string"},
                    "ports": {"type": "object", "description": "Map of container_port -> host_port"},
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

    async def _dispatch_tool(self, name: str, args: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        try:
            if name == "analyze_project":
                return self.projects.analyze_project(ProjectAnalysisRequest(**args)).model_dump()
            if name == "generate_dockerfile":
                return self.projects.generate_dockerfile(DockerfileGenerationRequest(**args)).model_dump()
            if name == "list_containers":
                items = await self.docker.list_containers(user_id)
                return {"containers": [c.model_dump() for c in items]}
            if name == "create_container":
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
        messages.append({"role": "user", "content": message})
        tool_calls_made: List[Dict[str, Any]] = []

        for _ in range(5):  # bounded tool-call loop
            resp = await client.chat.completions.create(
                model=config.model, messages=messages, tools=TOOLS,
                temperature=config.temperature, max_tokens=config.max_tokens, top_p=config.top_p,
            )
            choice = resp.choices[0].message
            if not choice.tool_calls:
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
        messages = list(history) + [{"role": "user", "content": message}]
        tool_calls_made: List[Dict[str, Any]] = []

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
