from pathlib import Path
import logging

logger = logging.getLogger(__name__)

ALLOWED_ROOT = Path("data")


class FileManager:
    def read(self, filepath: str) -> str:
        path = Path(filepath)
        if not self._is_allowed(path):
            return f"Acceso denegado: {filepath}"
        if not path.exists():
            return f"Archivo no encontrado: {filepath}"
        return path.read_text()

    def write(self, filepath: str, content: str) -> str:
        path = Path(filepath)
        if not self._is_allowed(path):
            return f"Acceso denegado: {filepath}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Escrito: {filepath}"

    def list_dir(self, dirpath: str = "data") -> list[str]:
        path = Path(dirpath)
        if not self._is_allowed(path):
            return []
        if not path.is_dir():
            return []
        return [str(f.relative_to(path)) for f in path.rglob("*") if f.is_file()]

    def _is_allowed(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(ALLOWED_ROOT.resolve())
            return True
        except ValueError:
            return False
