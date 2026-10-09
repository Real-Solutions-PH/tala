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
    embed_tokenizer: str = os.getenv("EMBED_TOKENIZER", "Qwen/Qwen3-Embedding-0.6B")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kapiling.db"

settings = Settings()
