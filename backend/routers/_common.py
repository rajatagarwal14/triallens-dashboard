"""Shared plumbing for the analytics routers: one filter dependency, and a helper that
fetches the full local dataset and runs a pure compute function over it."""
from typing import Any, Callable, Optional

from fastapi import Query

from services.datasets import Filters, manager


def common_filters(
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phases: Optional[str] = Query(None),
    studyTypes: Optional[str] = Query(None),
    sponsorClasses: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    fromYear: Optional[int] = Query(None, ge=2000, le=2030),
    completionFrom: Optional[str] = Query(None),
    completionTo: Optional[str] = Query(None),
    geoLat: Optional[float] = Query(None, ge=-90, le=90),
    geoLng: Optional[float] = Query(None, ge=-180, le=180),
    geoMiles: Optional[float] = Query(None, gt=0, le=12000),
) -> Filters:
    return Filters.from_query(
        condition=condition, status=status, phases=phases, studyTypes=studyTypes,
        sponsorClasses=sponsorClasses, country=country, fromYear=fromYear,
        completionFrom=completionFrom, completionTo=completionTo,
        geoLat=geoLat, geoLng=geoLng, geoMiles=geoMiles,
    )


async def analyse(filters: Filters, name: str, fn: Callable[[list], Any], extra: tuple = ()) -> dict:
    """Run `fn(studies)` over the dataset for these filters and attach coverage.
    Coverage reflects retrieval progress, so the UI can label partial results."""
    snap = await manager.snapshot(filters)
    payload = await manager.compute(snap, name, extra, fn)
    return {**payload, "coverage": snap.coverage}
