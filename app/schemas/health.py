from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    version: str
    environment: str


class DBHealthStatus(BaseModel):
    status: Literal["ok", "unavailable"]
    latency_ms: float | None = None
    error: str | None = None


class ReadinessStatus(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]
