from fastapi import APIRouter, Query
from typing import Optional
from services import ct_gov

router = APIRouter()


@router.get("/")
async def search(
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phases: Optional[str] = Query(None),
    studyTypes: Optional[str] = Query(None),
    sponsorClasses: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    fromYear: Optional[int] = Query(None, ge=2000, le=2030),
    sort: Optional[str] = Query(None),
    pageSize: int = Query(25, ge=1, le=100),
    pageToken: Optional[str] = Query(None),
):
    status_list = status.split(",") if status else None
    phase_list = phases.split(",") if phases else None
    study_type_list = studyTypes.split(",") if studyTypes else None
    sponsor_class_list = sponsorClasses.split(",") if sponsorClasses else None
    return await ct_gov.search_studies(
        condition=condition,
        status=status_list,
        phases=phase_list,
        study_types=study_type_list,
        sponsor_classes=sponsor_class_list,
        country=country,
        from_year=fromYear,
        sort=sort,
        page_size=pageSize,
        page_token=pageToken,
    )


@router.get("/{nct_id}")
async def get_study(nct_id: str):
    return await ct_gov.get_study(nct_id)
