import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    llm_url: str = os.getenv("LLM_URL", "http://127.0.0.1:8080")
    embed_url: str = os.getenv("EMBED_URL", "http://127.0.0.1:8082")
    rerank_url: str = os.getenv("RERANK_URL", "http://127.0.0.1:8083")
    whisper_url: str = os.getenv("WHISPER_URL", "http://127.0.0.1:8081")
    data_dir: Path = Path(os.getenv("KAPILING_DATA", ROOT / "data"))
    pair_key: str = os.getenv("KAPILING_KEY", "")
    demo: bool = os.getenv("KAPILING_DEMO", "0") == "1"
    worker: bool = os.getenv("KAPILING_WORKER", "1") == "1"   # the ingestion worker; tests set 0
    # Docling's PDF models (layout, TableFormer), fetched by scripts/fetch_models.sh; loaded from here, never the network.
    docling_artifacts: Path = Path(os.getenv("DOCLING_ARTIFACTS", Path.home() / "models" / "docling"))
    embed_tokenizer: str = os.getenv("EMBED_TOKENIZER", "Qwen/Qwen3-Embedding-0.6B")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kapiling.db"

settings = Settings()
