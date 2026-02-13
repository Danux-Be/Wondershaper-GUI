import logging
import signal
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RUNNING = True


def _handle_stop(signum: int, _frame: object) -> None:
    global RUNNING
    logger.info("worker shutdown signal received", extra={"signal": signum})
    RUNNING = False


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    logger.info("worker started (placeholder, no jobs yet)")
    while RUNNING:
        time.sleep(1)
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
