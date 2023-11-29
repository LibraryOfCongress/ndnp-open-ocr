import logging
import os

def setup_logging(log_filename='ndnp_open_ocr.log'):
    current_directory = os.getcwd()
    log_file_path = os.path.join(current_directory, log_filename)

    logger = logging.getLogger(__name__)

    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file_path)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger

# Configure and export the logger
logger = setup_logging()