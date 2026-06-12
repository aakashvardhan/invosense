"""Connect your Gmail account to Composio for the AP agent."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from composio_gmail import (  # noqa: E402
    get_gmail_connection_status,
    start_gmail_connection,
    wait_for_gmail_connection,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Connect Gmail to Composio")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait up to 2 minutes for OAuth to complete after opening the link",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the OAuth URL instead of opening a browser",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Only check whether Gmail is already connected",
    )
    args = parser.parse_args()

    try:
        if args.status:
            result = get_gmail_connection_status()
            print(result)
            return 0 if result.get("connected") else 1

        result = start_gmail_connection(open_browser=not args.no_browser)
        print("\nGmail connection started:")
        print(f"  user_id:              {result['user_id']}")
        print(f"  auth_config_id:       {result['auth_config_id']}")
        print(f"  connection_request_id:{result['connection_request_id']}")
        print(f"\nOpen this URL to sign in:\n  {result['redirect_url']}\n")

        if args.wait:
            print("Waiting for you to complete OAuth in the browser...")
            connected = wait_for_gmail_connection(result["connection_request_id"])
            print("Gmail connected successfully:")
            print(f"  connected_account_id: {connected['connected_account_id']}")
            print(f"  status:               {connected['status']}")
        else:
            print("Run again with --wait to block until OAuth finishes:")
            print("  python connect_gmail.py --wait")

        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
