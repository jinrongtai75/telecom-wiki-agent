import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key


ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class APIKeyManager:
    def __init__(self):
        load_dotenv(ENV_FILE)

    def _env_var(self, service: str) -> str:
        svc = service.upper()
        if svc == "WIKI_AGENT_PASSWORD":
            return "WIKI_AGENT_PASSWORD"
        return f"{svc}_API_KEY"

    def save_key(self, service: str, api_key: str) -> None:
        ENV_FILE.touch(exist_ok=True)
        env_var = self._env_var(service)
        set_key(str(ENV_FILE), env_var, api_key)
        os.environ[env_var] = api_key

    def get_key(self, service: str) -> Optional[str]:
        load_dotenv(ENV_FILE, override=True)
        return os.environ.get(self._env_var(service))

    def validate_key(self, service: str) -> bool:
        key = self.get_key(service)
        return bool(key and len(key.strip()) > 0)

    def list_services(self) -> dict:
        load_dotenv(ENV_FILE, override=True)
        return {
            "gemini": bool(os.environ.get("GEMINI_API_KEY")),
            "wiki_agent": bool(os.environ.get("WIKI_AGENT_PASSWORD")),
        }
