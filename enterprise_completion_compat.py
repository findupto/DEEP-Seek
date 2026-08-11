"""Runtime compatibility fixes for enterprise accounting primitives.

Keeps the original module API while normalizing money values, enforcing
one-shot idempotency keys, and returning stable two-decimal report values.
"""


def install():
    import enterprise_completion_patch as e
    if getattr(e, "_compat_fixed", False):
        return e

    from decimal import Decimal

    old_issue_cost = e.issue_cost

    def issue_cost(*args, **kwargs):
        return f"{Decimal(str(old_issue_cost(*args, **kwargs))):.2f}"

    e.issue_cost = issue_cost

    old_journal = e.journal

    def journal(c, event_type, source_id, store_id, lines, memo=""):
        normalized = []
        for item in lines:
            row = dict(item)
            for key in ("debit", "credit"):
                if key in row:
                    row[key] = str(row[key])
            normalized.append(row)
        return old_journal(c, event_type, source_id, store_id, normalized, memo)

    e.journal = journal

    old_queue = e.queue_sync

    def queue_sync(c, key, payload):
        existing = c.execute(
            "SELECT status,payload_hash FROM ent_sync WHERE idempotency_key=?", (key,)
        ).fetchone()
        if existing:
            return False
        return old_queue(c, key, payload)

    e.queue_sync = queue_sync

    old_p_and_l = e.p_and_l

    def p_and_l(*args, **kwargs):
        result = dict(old_p_and_l(*args, **kwargs))
        for key in ("revenue", "expenses", "net_profit"):
            if key in result:
                result[key] = f"{Decimal(str(result[key])):.2f}"
        return result

    e.p_and_l = p_and_l

    e._compat_fixed = True
    return e


install()
