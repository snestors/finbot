from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_path: str = "data/finbot.db"

    # LLM — Claude (primary) + Gemini (fallback)
    claude_api_token: str = ""
    claude_model: str = "claude-sonnet-4-6"
    google_ai_api_key: str = ""

    # Server
    port: int = 8080
    timezone: str = "America/Lima"

    # WhatsApp
    whatsapp_my_number: str = ""
    bridge_port: int = 3001

    # Cloudflare (opcional)
    tunnel_name: str = "finbot"
    tunnel_domain: str = ""

    # MCP servers
    mcp_servers_config: str = "data/mcp_servers.json"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    # RPi optimizations
    uvicorn_workers: int = 1
    max_chat_history_cache: int = 100

    # Receipts storage
    receipts_dir: str = "data/receipts"

    # Auth
    auth_pin_hash: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def bridge_url(self) -> str:
        return f"http://localhost:{self.bridge_port}"


settings = Settings()
