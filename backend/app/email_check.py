import argparse
import logging

from app.config import get_settings
from app.services.mail_service import check_smtp_readiness, send_delivery_test

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Folio's production email delivery")
    parser.add_argument("--to", help="Send a delivery test to this address after probing SMTP")
    args = parser.parse_args()
    settings = get_settings()

    try:
        check_smtp_readiness(settings)
        print("SMTP readiness check passed")
        if args.to:
            send_delivery_test(settings, email=args.to)
            print(f"Delivery test accepted for {args.to}")
    except Exception as error:
        logger.exception("Email delivery check failed")
        raise SystemExit(f"Email delivery check failed: {error}") from error


if __name__ == "__main__":
    main()
