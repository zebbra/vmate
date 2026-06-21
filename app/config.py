from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    label_selector: str = "app.kubernetes.io/instance=victoria-metrics-agent"
    namespace: str = "monitoring"
    vmagent_port: int = 8429
    poll_interval: int = 60  # seconds
    vmagent_timeout: int = 10  # seconds per pod request

    # comma-separated job names excluded from unhealthy_target_info metric and /unhealthy endpoints
    ignore_info_jobs: list[str] = []
    # comma-separated job names excluded from all target count metrics
    ignore_health_jobs: list[str] = []

    @field_validator("ignore_info_jobs", "ignore_health_jobs", mode="before")
    @classmethod
    def _parse_csv(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [j.strip() for j in v.split(",") if j.strip()]
        return v  # type: ignore[return-value]

    class Config:
        env_prefix = "VMTE_"


settings = Settings()
