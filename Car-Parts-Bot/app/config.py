import os
from dotenv import load_dotenv
import pymysql
load_dotenv()
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if isinstance(value, str):
        return value.strip()
    return value


@dataclass
class AppConfig:
    SECRET_KEY: str = _env("SECRET_KEY", "dev-secret") or "dev-secret"
    # SQLALCHEMY_DATABASE_URI: str = (
    #     _env("DATABASE_URL")
    #     or (
    #         f"mysql+pymysql://{_env('DB_USER','root')}:{_env('DB_PASSWORD','')}@"
    #         f"{_env('DB_HOST','127.0.0.1')}:{_env('DB_PORT','3306')}/{_env('DB_NAME','carparts')}"
    #     )
    # )
    SQLALCHEMY_DATABASE_URI: str = (
        _env("DATABASE_URL")
        or (
            f"mysql+pymysql://{_env('DB_USER','finelan1_2020')}:{_env('DB_PASSWORD','JZ3xzj$R9s;H')}@"
            f"{_env('DB_HOST','box2329.bluehost.com')}:{_env('DB_PORT','3306')}/{_env('DB_NAME','finelan1_new2020')}"
        )
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,     # 1 hour
    "pool_size": 3,           # 🔥 VERY IMPORTANT
    "max_overflow": 0,        # 🔥 NO burst connections
    "connect_args": {
        "connect_timeout": 8,
    },
    }

    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # External services
    OPENAI_API_KEY = _env("OPENAI_API_KEY")
    OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")

    META_VERIFY_TOKEN: str | None = _env("META_VERIFY_TOKEN")
    META_ACCESS_TOKEN: str | None = _env("META_ACCESS_TOKEN")
    META_PHONE_NUMBER_ID: str | None = _env("META_PHONE_NUMBER_ID")
    # wpbusiness account id : 1158701849734296
    META_BUSINESS_ID=1878244812926215

    CHASSIS_API_BASE_URL: str | None = _env("CHASSIS_API_BASE_URL")
    CHASSIS_API_KEY: str | None = _env("CHASSIS_API_KEY")
    # IMAGE_OCR_PROVIDER: str = _env("IMAGE_OCR_PROVIDER", "tesseract") or "tesseract"
    # TESSERACT_CMD: str | None = _env("TESSERACT_CMD")
    # TESSERACT_LANG: str = _env("TESSERACT_LANG", "eng") or "eng"
    # Admin & Sales
    ADMIN_TOKEN: str = _env("ADMIN_TOKEN", "admin-token") or "admin-token"
    SALES_AGENTS: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Populate SALES_AGENTS safely (avoid mutable default at class level)."""
        sales_agents_env = _env("SALES_AGENTS")
        if sales_agents_env:
            self.SALES_AGENTS = [a.strip() for a in sales_agents_env.split(",") if a.strip()]
        else:
            self.SALES_AGENTS = ["agent1", "agent2", "agent3"]


