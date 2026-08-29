import os
from pathlib import Path


# settings.py -> config -> Coding-Agent-Main
PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODEL_FLASH = "deepseek-v4-flash"
MODEL_PRO = "deepseek-v4-pro"
MODEL_VISION = "deepseek-v4-flash-vision-exp"
AVAILABLE_MODELS = (MODEL_FLASH, MODEL_PRO, MODEL_VISION)
DEFAULT_MODEL = MODEL_FLASH


def _load_dotenv() -> None:
    """读取项目根目录的 .env；已有系统环境变量优先。"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def get_api_key() -> str:
    _load_dotenv()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY，请先设置环境变量。")
    return key
