from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AgentTask:
    """Mirrors specs/schemas/agent-task.schema.json - every field is required deliberately."""

    task_id: str
    role: str
    objective: str
    output_format: str
    allowed_tools: list[str]
    boundaries: str
    budget: dict
    parent_task_id: str | None = None

    def to_schema_dict(self) -> dict:
        return {
            "taskId": self.task_id,
            "role": self.role,
            "objective": self.objective,
            "outputFormat": self.output_format,
            "allowedTools": self.allowed_tools,
            "boundaries": self.boundaries,
            "budget": self.budget,
            "parentTaskId": self.parent_task_id,
        }

    @staticmethod
    def from_schema_dict(data: dict) -> AgentTask:
        return AgentTask(
            task_id=data["taskId"],
            role=data["role"],
            objective=data["objective"],
            output_format=data["outputFormat"],
            allowed_tools=data["allowedTools"],
            boundaries=data["boundaries"],
            budget=data["budget"],
            parent_task_id=data.get("parentTaskId"),
        )


@dataclass
class AgentResult:
    task_id: str
    role: str
    text: str
    artifact_refs: list[dict] = field(default_factory=list)
    status: Literal["ok", "partial", "error"] = "ok"
