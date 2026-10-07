"""Display helpers for money and scores."""


def format_usd(value):
    if value is None:
        return "—"
    amount = int(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1_000_000_000:
        text = f"{amount / 1_000_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{sign}${text}B"
    if amount >= 1_000_000:
        text = f"{amount / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{sign}${text}M"
    return f"{sign}${amount:,}"


def format_score(value):
    if value is None:
        return None
    rounded = round(float(value), 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}"
