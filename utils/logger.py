# utils/logger.py
import logging
import sys

def setup_logger():
    log_format = "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    logger = logging.getLogger("PolyCopyBot")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logger()
