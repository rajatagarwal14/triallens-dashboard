"""
"New trials" alert — trials newly REGISTERED (first posted to ClinicalTrials.gov)
within a recent window for the active indication + filters. Powers the bell.
"""
import datetime
from fastapi import APIRouter, Query
from typing import Optional
from services import ct_gov

router = APIRouter()


def _csv(v: Optional[str]):
    return v.split(",") if v else None


@router.get("/")
async def get_alerts(
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phases: Optional[str] = Query(None),
    studyTypes: Optional[str] = Query(None),
    sponsorClasses: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    fromYear: Optional[int] = Query(None, ge=2000, le=2030),
    days: int = Query(30, ge=1, le=365),
):
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    result = await ct_gov.search_studies(
        condition=condition, status=_csv(status), phases=_csv(phases),
        study_types=_csv(studyTypes), sponsor_classes=_csv(sponsorClasses),
        country=country, from_year=fromYear, first_posted_from=since,
        sort="StudyFirstPostDate:desc", page_size=50,
    )
    trials = [
        {
            "nctId": s["nctId"], "title": s["title"],
            "sponsor": s.get("sponsor", {}).get("name", ""),
            "phase": (s.get("phases") or ["NA"])[0],
            "status": s.get("status", ""),
            "firstPostDate": s.get("firstPostDate"),
            "countryCount": s.get("countryCount", 0),
        }
        for s in result["studies"]
    ]
    return {
        "since": since,
        "days": days,
        "count": result["totalCount"],
        "trials": trials,
    }
