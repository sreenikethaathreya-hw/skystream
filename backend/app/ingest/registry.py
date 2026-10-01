from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from app.ingest.exports import validate_hierarchy, validate_market, validate_plan
from app.ingest.exports_share import validate_competitors, validate_grower
from app.ingest.lookups import ImportContext
from app.ingest.report import ImportReport
from app.ingest.templates import validate_actuals, validate_assignments, validate_seasonality

Validator = Callable[[pd.DataFrame, ImportContext], tuple[list[dict], ImportReport]]


@dataclass(frozen=True)
class UploadKind:
    kind: str
    label: str
    source: str
    required: bool
    validator: Validator
    sheets: tuple[str, ...] = ()


# Order is the recommended upload order: the hierarchy first, because every figure is keyed on it.
# Every kind has a downloadable template in app/ingest/template_files.py.
UPLOAD_KINDS: dict[str, UploadKind] = {
    k.kind: k
    for k in (
        UploadKind(
            "hierarchy",
            "Product hierarchy",
            "Prod Hierarchy workbook, tab 'prod hierarchy', or the template",
            True,
            validate_hierarchy,
            ("prod hierarchy",),
        ),
        UploadKind("market", "Market", "i-MAPS MAPSHistData export, or the template", True, validate_market),
        UploadKind(
            "plan", "Syngenta plan", "i-MAPS Syngenta5YrsSales export, or the template", True, validate_plan
        ),
        UploadKind(
            "competitors",
            "Competitor shares",
            "i-MAPS CompetitorMktShare export, or the template",
            True,
            validate_competitors,
        ),
        UploadKind(
            "actuals",
            "Monthly actuals",
            "Monthly SAP sales extract in the template format",
            True,
            validate_actuals,
        ),
        UploadKind(
            "assignments",
            "Rep assignments",
            "Users and their segments in the template format",
            True,
            validate_assignments,
        ),
        UploadKind(
            "grower",
            "Grower potential",
            "CRM grower-potential export, or the template",
            False,
            validate_grower,
        ),
        UploadKind(
            "seasonality",
            "Seasonality",
            "Monthly weights in the template format",
            False,
            validate_seasonality,
        ),
    )
}
