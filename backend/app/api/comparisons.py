from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import select

from app.models import Section, Source
from app.schemas import Strict
from app.security import CurrentUser, Db, throttle
from app.services.comparison import ComparisonLimitError, compare_sections
from app.services.resources import audit, owned, source_dict

router = APIRouter()


class ComparisonInput(Strict):
    source_ids: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(min_length=2, max_length=2)


@router.post("/comparisons")
def compare_sources(data: ComparisonInput, db: Db, user: CurrentUser):
    throttle(db, "comparison:" + user.id, 30, 3600)
    if data.source_ids[0] == data.source_ids[1]:
        raise HTTPException(422, "Select two different retained source versions.")
    sources = [owned(db, Source, source_id, user) for source_id in data.source_ids]
    if any(source.status not in {"READY", "PARTIAL"} for source in sources):
        raise HTTPException(409, "Wait for text extraction to finish for both sources.")
    sections = [
        [
            row.data
            for row in db.scalars(
                select(Section).where(Section.source_id == source.id).order_by(Section.ordinal)
            )
        ]
        for source in sources
    ]
    if any(not group for group in sections):
        raise HTTPException(409, "Both sources need retained extracted text before comparison.")
    try:
        comparison = compare_sections(*sections)
    except ComparisonLimitError as exc:
        raise HTTPException(422, str(exc)) from None
    audit(db, user.id, "source.compared", sources[0].id)
    db.commit()
    return {"sources": [source_dict(source) for source in sources], **comparison}
