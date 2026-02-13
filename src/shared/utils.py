import logging
import os

# LOGGING CONFIGURATION
LOG_LEVEL = logging.INFO

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Output to console
        # logging.FileHandler(os.path.join(log_dir, "app.log"))  # Output to file
    ],
)


def get_logger(name: str):
    return logging.getLogger(name)
