"""Central configuration. Every secret and tunable lives here, sourced from .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # Locked by scripts/benchmark_nim.py. Blank per-task overrides fall back to
    # nvidia_model so the common case stays a single knob.
    nvidia_model: str = ""
    nvidia_model_tutor: str = ""
    nvidia_model_structured: str = ""
    nvidia_model_backup: str = ""
    nvidia_model_vision: str = ""

    # Chosen by scripts/benchmark_embed.py: best cross-lingual retrieval of the
    # models this key can reach (83% vs 75%/67% for the alternatives).
    nvidia_embed_model: str = "nvidia/nemotron-3-embed-1b"
    nvidia_embed_dim: int = 2048

    # Calibrated by scripts/calibrate_threshold.py against the demo textbook:
    # in-scope questions score >= 0.184, out-of-scope <= 0.118. Do not raise this
    # without re-running the calibration — 0.45 refused 10 of 12 valid questions.
    grounding_threshold: float = 0.15
    retrieval_top_k: int = 6

    # Small chunks measurably sharpen retrieval: at 120 tokens the in/out
    # separation gap is +0.065 versus +0.021 at 500, because a large chunk
    # dilutes the topical match. top_k=6 keeps enough context to teach from.
    chunk_size: int = 120
    chunk_overlap: int = 25

    data_dir: Path = ROOT / "data"
    db_path: Path = ROOT / "data" / "bodhi.db"

    @property
    def tutor_model(self) -> str:
        return self.nvidia_model_tutor or self.nvidia_model

    @property
    def structured_model(self) -> str:
        return self.nvidia_model_structured or self.nvidia_model

    @property
    def vision_model(self) -> str:
        return self.nvidia_model_vision or self.nvidia_model

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"


settings = Settings()

for _d in (settings.data_dir, settings.cache_dir, settings.index_dir):
    _d.mkdir(parents=True, exist_ok=True)
