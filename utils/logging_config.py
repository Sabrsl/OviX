"""
Configuration centralisée du logging pour l'application.
"""

import logging
import sys
from pathlib import Path
from typing import List


class LogCapture(logging.Handler):
    """Handler personnalisé pour capturer les logs en mémoire pour l'affichage UI."""
    def __init__(self, max_lines=1000):
        super().__init__()
        self.logs = []
        self.max_lines = max_lines
    
    def emit(self, record):
        """Capture le log et le stocke en mémoire."""
        log_entry = self.format(record)
        self.logs.append(log_entry)
        # Garder seulement les max_lines derniers logs
        if len(self.logs) > self.max_lines:
            self.logs = self.logs[-self.max_lines:]
    
    def get_recent_logs(self, count=100):
        """Retourne les count derniers logs."""
        return self.logs[-count:] if len(self.logs) > count else self.logs
    
    def clear_logs(self):
        """Efface tous les logs capturés."""
        self.logs = []


# Instance globale du captureur
_log_capture = None


def get_log_capture() -> LogCapture:
    """Retourne l'instance globale du captureur de logs."""
    global _log_capture
    if _log_capture is None:
        _log_capture = LogCapture()
    return _log_capture


def setup_logging() -> None:
    """Configure le logging pour l'application."""
    global _log_capture

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    if _log_capture is None:
        _log_capture = LogCapture()

    # Force unbuffered output
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # Configurer le logging si pas déjà configuré
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_dir / "app.log", encoding='utf-8'),
                _log_capture
            ],
            force=True  # Force reconfiguration even if already configured
        )

    # Ensure uvicorn logs are also visible
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
