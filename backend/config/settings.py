"""Configurações centralizadas do sistema."""

from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Settings:
    # ── Salesforce ──────────────────────────────────────
    SF_BASE_URL: str = "https://cooxupexyz2023--qa.sandbox.my.salesforce.com"
    SF_API_VERSION: str = "v59.0"

    # ── Chrome ──────────────────────────────────────────
    CHROME_PROFILE_PATH: str = ""  # Preenchido em runtime via env ou auto-detect

    # ── Paths ───────────────────────────────────────────
    PROJECT_ROOT: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)

    @property
    def DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / "data"

    @property
    def BACKUPS_DIR(self) -> Path:
        return self.DATA_DIR / "backups"

    @property
    def LOGS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "logs"

    @property
    def PLANILHAS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "Planilhas bases"

    @property
    def DB_PATH(self) -> Path:
        return self.DATA_DIR / "rpa.db"

    # ── Server ──────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Limites ─────────────────────────────────────────
    COMPOSITE_BATCH_SIZE: int = 200   # Máx IDs por chamada Composite API
    BULK_THRESHOLD: int = 10_000      # Acima disso, usa Bulk API 2.0
    REQUEST_TIMEOUT: int = 30         # Timeout HTTP em segundos
    MAX_RETRIES: int = 3              # Retentativas em erro 5xx

    def __post_init__(self):
        """Cria diretórios necessários."""
        self.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Auto-detect Chrome profile path
        if not self.CHROME_PROFILE_PATH:
            import os
            default = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
            if default.exists():
                self.CHROME_PROFILE_PATH = str(default)


settings = Settings()
