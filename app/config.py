from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)
from typing import Any, Tuple, Type

_CSV_FIELDS = {"ignore_info_jobs", "ignore_health_jobs"}


class _CsvEnvSource(EnvSettingsSource):
    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        if field_name in _CSV_FIELDS and isinstance(value, str):
            return [j.strip() for j in value.split(",") if j.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    label_selector: str = "app.kubernetes.io/instance=victoria-metrics-agent"
    namespace: str = "monitoring"
    log_level: str = "INFO"
    vmagent_port: int = 8429
    poll_interval: int = (
        113  # seconds (prime to avoid phase-lock with scrape intervals)
    )
    vmagent_timeout: int = 10  # seconds per pod request

    # comma-separated job names excluded from unhealthy_target_info metric and /unhealthy endpoints
    ignore_info_jobs: list[str] = []
    # comma-separated job names excluded from all target count metrics
    ignore_health_jobs: list[str] = []

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _CsvEnvSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    class Config:
        env_prefix = "VMTE_"


settings = Settings()
