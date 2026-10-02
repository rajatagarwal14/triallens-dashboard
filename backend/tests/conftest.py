import pathlib
import sys

# Make `import main`, `import services...` work when pytest runs from backend/.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def make_study(nct="NCT00000001", **over):
    """A normalized study dict shaped like ct_gov._norm_study output."""
    s = {
        "nctId": nct, "title": "t", "officialTitle": "", "status": "RECRUITING",
        "phases": ["PHASE2"], "studyType": "INTERVENTIONAL", "summary": "",
        "conditions": ["Melanoma"], "keywords": [], "interventions": [],
        "sponsor": {"name": "Acme", "class": "INDUSTRY"},
        "enrollment": {"count": 100, "type": "ESTIMATED"},
        "startDate": "2024-01", "completionDate": None,
        "primaryCompletionDate": "2027-06", "primaryCompletionType": "ESTIMATED",
        "firstPostDate": "2024-01-02", "lastUpdateDate": "2025-01-01",
        "eligibility": {"criteria": "", "healthyVolunteers": False, "sex": "ALL",
                        "minimumAge": "18 Years", "maximumAge": "N/A"},
        "countries": {"United States": 1}, "sites": [], "locations": [], "officials": [],
        "countryCount": 1, "siteCount": 0,
    }
    s.update(over)
    return s


import pytest


@pytest.fixture
def api(tmp_path, monkeypatch):
    """TestClient whose dataset layer is fed from an in-memory list of studies."""
    from fastapi.testclient import TestClient
    import main
    from services import datasets

    state = {"studies": []}

    async def fake_fetch(*, page_size=1000, page_token=None, client=None, **filters):
        s = state["studies"]
        return {"studies": s, "totalCount": len(s), "nextPageToken": None}

    mgr = datasets.manager
    monkeypatch.setattr(mgr, "_fetch_page", fake_fetch)
    monkeypatch.setattr(mgr, "cache_dir", tmp_path)
    monkeypatch.setattr(mgr, "page_delay", 0)
    mgr._mem.clear()
    mgr._memo.clear()

    def load(studies):
        state["studies"] = studies
        mgr._mem.clear()
        mgr._memo.clear()
        return TestClient(main.app)

    return load
