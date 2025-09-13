import logging
import os

# Create logs directory if it doesn't exist
log_dir = "./logs"
os.makedirs(log_dir, exist_ok=True)

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
