"""
Logging centralizado — Brabo Analytics.

Uso:
    from logger import get_logger          # quando src/ está no sys.path
    from src.logger import get_logger      # quando workspace root está no sys.path

    logger = get_logger("frontend")
    logger.info("Mensagem")
    logger.exception("Erro inesperado")  # inclui traceback completo
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[1] / "logs"

_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s — %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado com console + arquivo rotativo.

    Idempotente: chamar duas vezes com o mesmo nome retorna o mesmo logger
    sem duplicar handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    try:
        LOGS_DIR.mkdir(exist_ok=True)
        fh = RotatingFileHandler(
            LOGS_DIR / "app.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        logger.warning("Não foi possível criar o arquivo de log em %s", LOGS_DIR)

    return logger
