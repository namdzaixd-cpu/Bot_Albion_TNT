"""Atomic SP snapshot import: totals and the parsed log watermark commit in one RPC."""


def import_sp_snapshot(data: dict, client) -> dict:
    totals = [
        {"player_name": str(user_id), "amount": int(amount)}
        for user_id, amount in data.get("history", {}).items()
    ]
    response = client.rpc(
        "import_siphoned_snapshot",
        {"p_totals": totals, "p_last_update": data.get("last_update")},
    ).execute()
    result = getattr(response, "data", None)
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    if not isinstance(result, dict):
        raise RuntimeError("SP snapshot RPC returned no committed result")
    return result
