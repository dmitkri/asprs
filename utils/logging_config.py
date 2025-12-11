import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging(log_dir='logs', log_level=logging.INFO):
    os.makedirs(log_dir, exist_ok=True)
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_handler)
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info(f"Логирование инициализировано: {datetime.now()}")
    logger.info(f"Уровень логирования: {logging.getLevelName(log_level)}")
    logger.info("=" * 50)
    return logger

def get_logger(name):
    return logging.getLogger(name)

setup_logging()




