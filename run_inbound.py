#!/usr/bin/env python3
"""
Start the inbound email processor as a background service.

Usage:
    python run_inbound.py              # Run once
    python run_inbound.py --poll      # Run continuously (5-minute intervals)
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lib.inbox_processor import start_inbox_processor, InboxProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Start inbound email processor")
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Run continuously with polling (default: run once)"
    )
    args = parser.parse_args()

    if args.poll:
        logger.info("Starting inbox processor with continuous polling...")
        processor = start_inbox_processor()

        # Keep the main thread alive
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down inbox processor...")
            processor.stop_polling()
    else:
        logger.info("Running inbox processor once...")
        processor = InboxProcessor()
        processor.process_emails()
        logger.info("Inbox processing complete.")


if __name__ == "__main__":
    main()
