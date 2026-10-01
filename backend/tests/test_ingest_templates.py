import pytest

from app.ingest.lookups import ImportContext, normalize
from app.ingest.reader import read_upload
from app.ingest.registry import UPLOAD_KINDS
from app.ingest.template_files import TEMPLATES, template_csv


def _validate(kind: str, ctx: ImportContext):
    frame = read_upload(template_csv(kind).encode(), f"{kind}-template.csv", list(UPLOAD_KINDS[kind].sheets))
    return UPLOAD_KINDS[kind].validator(frame, ctx)


@pytest.fixture
def ctx() -> ImportContext:
    context = ImportContext(country_aliases={"ES": "ES", "SPAIN": "ES"}, grower_ha_cap=500.0)
    rows, _ = _validate("hierarchy", context)
    for r in rows:
        context.segment_ids.add(r["id"])
        context.segment_by_desc[normalize(r["description"])] = r["id"]
        context.mega_by_segment[r["id"]] = r["megaSegmentId"]
    return context


def test_every_upload_kind_has_a_template() -> None:
    assert set(TEMPLATES) == set(UPLOAD_KINDS)


@pytest.mark.parametrize("kind", list(UPLOAD_KINDS))
def test_template_passes_its_own_validator(kind: str, ctx: ImportContext) -> None:
    rows, report = _validate(kind, ctx)
    assert rows, kind
    assert report.rejected == 0, report.rejects
    unexpected = {m for m in report.warnings if "filled from the plan net price" not in m}
    assert not unexpected, unexpected
