import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key


ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class APIKeyManager:
    def __init__(self):
        load_dotenv(ENV_FILE)

    def save_key(self, service: str, api_key: str) -> None:
        ENV_FILE.touch(exist_ok=True)
        env_var = "JIHYE_TOKEN" if service.upper() == "JIHYE" else f"{service.upper()}_API_KEY"
        set_key(str(ENV_FILE), env_var, api_key)
        os.environ[env_var] = api_key

    def get_key(self, service: str) -> Optional[str]:
        load_dotenv(ENV_FILE, override=True)
        if service.upper() == "JIHYE":
            return os.environ.get("JIHYE_TOKEN")
        return os.environ.get(f"{service.upper()}_API_KEY")

    def validate_key(self, service: str) -> bool:
        key = self.get_key(service)
        return bool(key and len(key.strip()) > 0)

    def list_services(self) -> dict:
        load_dotenv(ENV_FILE, override=True)
        return {
            "jihye": bool(os.environ.get("JIHYE_TOKEN")),
        }
