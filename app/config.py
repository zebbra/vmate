from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    label_selector: str = "app.kubernetes.io/instance=victoria-metrics-agent"
    namespace: str = "monitoring"
    vmagent_port: int = 8429
    poll_interval: int = 60  # seconds
    vmagent_timeout: int = 10  # seconds per pod request

    class Config:
        env_prefix = "VMTE_"


settings = Settings()
