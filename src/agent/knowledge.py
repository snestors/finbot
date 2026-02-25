from pathlib import Path
from datetime import datetime

KNOWLEDGE_DIR = Path("data/knowledge")


class KnowledgeManager:
    def __init__(self):
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    def read(self, filename: str) -> str:
        path = KNOWLEDGE_DIR / filename
        return path.read_text() if path.exists() else ""

    def write(self, filename: str, content: str):
        (KNOWLEDGE_DIR / filename).write_text(content)

    def append(self, filename: str, entry: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(KNOWLEDGE_DIR / filename, "a") as f:
            f.write(f"\n[{timestamp}] {entry}")

    def list_docs(self) -> list[str]:
        return [f.name for f in KNOWLEDGE_DIR.glob("*.md")]
