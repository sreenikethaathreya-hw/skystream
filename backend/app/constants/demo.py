from dataclasses import dataclass


@dataclass(frozen=True)
class DemoUser:
    id: str
    name: str
    role: str
    title: str


DEMO_USERS = {
    "rep-a": DemoUser("rep-a", "Rep A", "rep", "Sales rep, autumn cycles"),
    "rep-b": DemoUser("rep-b", "Rep B", "rep", "Sales rep, early and spring cycles"),
    "lead": DemoUser("lead", "Consensus lead", "lead", "Product specialist, runs consensus"),
    "admin": DemoUser("admin", "Data admin", "admin", "Uploads data and manages users"),
}

# Used when the grower-potential upload has no Syngenta varieties for the selected crop.
SYNGENTA_VARIETIES = ["Hokkaido", "Saitama", "Leontes", "Bokken", "Kaamos", "Akame", "Norris", "Carlomagno"]
MAX_VARIETY_OPTIONS = 12

WEAK_HIT_RATE = 0.6
WEAK_BIAS = 0.1
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

PROFILE_LABELS = {
    "spring": "Spring",
    "autumn_early": "Autumn early",
    "autumn_medium": "Autumn medium",
    "autumn_late": "Autumn late",
    "autumn": "Autumn",
    "summer": "Summer",
    "winter": "Winter",
    "main": "Main",
}
