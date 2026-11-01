"""Admin CLI. Usage: uv run python -m app.admin erase-lead <lead_id> --actor you@example.com"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from app.db import get_sessionmaker
from app.services.privacy import erase_lead


async def _erase(lead_id: int, actor: str) -> None:
    async with get_sessionmaker()() as db:
        done = await erase_lead(db, lead_id, f"admin:{actor}", datetime.now(UTC))
        await db.commit()
    print("erased" if done else "nothing to erase (unknown or already erased)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.admin")
    sub = parser.add_subparsers(dest="command", required=True)
    erase = sub.add_parser("erase-lead", help="DPDP: erase a lead's personal data")
    erase.add_argument("lead_id", type=int)
    erase.add_argument("--actor", required=True, help="who requested/approved the erasure")
    args = parser.parse_args()
    asyncio.run(_erase(args.lead_id, args.actor))


if __name__ == "__main__":
    main()
