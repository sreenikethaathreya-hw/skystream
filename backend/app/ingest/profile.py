def profile_for(description: str) -> str:
    """Cycle profile from a micro-segment description, used for labels (e.g. 'Autumn late')."""
    upper = description.upper()
    if "SPRING" in upper:
        return "spring"
    for stage in ("EARLY", "MEDIUM", "LATE"):
        if f"AUTUMN-{stage}" in upper:
            return f"autumn_{stage.lower()}"
    if "AUTUMN" in upper:
        return "autumn"
    if "SUMMER" in upper:
        return "summer"
    if "WINTER" in upper:
        return "winter"
    return "main"
