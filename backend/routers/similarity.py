from fastapi import APIRouter, HTTPException
from services import ct_gov, similarity as sim_svc

router = APIRouter()


@router.get("/{nct_id}")
async def get_similar(nct_id: str):
    target = await ct_gov.get_study(nct_id)
    if not target:
        raise HTTPException(404, "Study not found")

    condition = target["conditions"][0] if target["conditions"] else None
    if not condition:
        return {"target": target, "similar": []}

    candidates = await ct_gov.get_studies_for_similarity(condition)
    similar = sim_svc.compute_similarities(target, candidates)
    return {"target": target, "similar": similar}
