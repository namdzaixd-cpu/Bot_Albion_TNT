"""Record an operator's evidence-backed CoreBank reconciliation decision.

This helper never calls UnbelievaBoat. Confirm the provider outcome independently
before running it; `not_paid` makes a credit eligible only after a fresh reaction
sequence, and `refund_not_applied` restores the credited state so an Officer can
re-add then remove the reaction to explicitly start a new refund attempt.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BOT_ROOT = REPO_ROOT / "bot"
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from core.db import execute  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message-id", required=True, help="Core ledger key, usually Discord message ID plus emoji key")
    parser.add_argument(
        "--decision",
        required=True,
        choices=("paid", "not_paid", "refund_applied", "refund_not_applied"),
        help="Decision supported by independent UnbelievaBoat evidence",
    )
    parser.add_argument("--actor-id", required=True, help="Discord ID of the operator making this decision")
    parser.add_argument("--evidence", required=True, help="Evidence reference or concise audit note")
    parser.add_argument("--guild-id", help="Required to complete a legacy row without a guild snapshot")
    parser.add_argument("--recipient-id", help="Required to complete a legacy row without a recipient snapshot")
    parser.add_argument("--emoji-key", help="Required to complete a legacy row without an emoji snapshot")
    parser.add_argument("--core-name", help="Required to complete a legacy row without a name snapshot")
    parser.add_argument("--core-display", help="Required to complete a legacy row without a display snapshot")
    return parser


def reconcile(args) -> dict:
    if not args.actor_id.strip() or not args.evidence.strip():
        raise ValueError("--actor-id and --evidence must not be blank")
    params = {
        "p_message_id": args.message_id,
        "p_decision": args.decision,
        "p_actor_id": args.actor_id.strip(),
        "p_evidence": args.evidence.strip(),
        "p_guild_id": args.guild_id,
        "p_recipient_id": args.recipient_id,
        "p_emoji_key": args.emoji_key,
        "p_core_name": args.core_name,
        "p_core_display": args.core_display,
    }
    response, error = execute(
        lambda client: client.rpc("reconcile_core_credit", params),
        retries=1,
    )
    if error:
        raise RuntimeError(f"Core reconciliation was not saved: {error}")
    result = getattr(response, "data", None) if response is not None else None
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    if not isinstance(result, dict) or not result.get("status"):
        raise RuntimeError("Core reconciliation RPC returned no committed status")
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = reconcile(args)
    except Exception as exc:
        print(f"Reconciliation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "retryable":
        print("Next step: Officer must remove and re-add the reaction to explicitly start a new credit attempt.")
    elif result["status"] == "credited" and args.decision == "refund_not_applied":
        print("Next step: Officer must re-add then remove the reaction to explicitly start a new refund attempt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
