from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Task(BaseModel):
    id: str
    description: str
    context: dict = Field(default_factory=dict)
    conventions: dict = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    level: int = 0
    assigned_model: str = "openai:gpt-4o-mini"

    @property
    def output_file(self) -> Optional[str]:
        return self.context.get("output_file")

    @property
    def related_files(self) -> List[str]:
        return self.context.get("related_files", [])


class Wave(BaseModel):
    level: int
    tasks: List[Task] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    task_results: List[dict] = Field(default_factory=list)


class ProviderConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    timeout: int = 60
    retry_count: int = 3


class TaskTemplate(BaseModel):
    fields: List[str] = Field(default_factory=list)
    decomposer_instructions: str = ""
