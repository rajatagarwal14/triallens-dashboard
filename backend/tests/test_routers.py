"""Regression tests for the reviewed API bugs, exercised through the real routes."""
import datetime
import pathlib

from conftest import make_study

TODAY = datetime.date.today()


def loc(facility, status=None, country="United States", city="Boston", lat=42.3, lon=-71.0):
    return {"facility": facility, "city": city, "country": country, "status": status, "lat": lat, "lon": lon}


# ── Finding 1: path traversal ───────────────────────────────────────────────
def test_static_fallback_cannot_escape_the_build_folder(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import main
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>SPA</html>")
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    app = FastAPI()
    main.mount_frontend(app, dist)
    c = TestClient(app)
    for attack in ["/%2e%2e/secret.txt", "/..%2fsecret.txt", "/%2e%2e/%2e%2e/etc/passwd",
                   "/assets/%2e%2e/%2e%2e/secret.txt"]:
        r = c.get(attack)
        assert "TOP SECRET" not in r.text, attack
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "SPA" in r.text            # only ever the app shell
    assert "SPA" in c.get("/some/client/route").text
    assert c.get("/api/nope").status_code == 404


# ── Findings 4 & 5: sites ───────────────────────────────────────────────────
def test_site_status_is_exact_and_site_status_beats_trial_status(api):
    c = api([make_study("NCT00000001", status="RECRUITING",
                        locations=[loc("Open Site", "RECRUITING"),
                                   loc("Closed Site", "ACTIVE_NOT_RECRUITING"),
                                   loc("Legacy Site", None)])])
    rows = {r["facility"]: r for r in c.get("/api/sites/?condition=x").json()["sites"]}
    assert rows["Open Site"]["enrollRate"] == 100
    assert rows["Closed Site"]["enrollRate"] == 0          # trial RECRUITING must not override
    assert rows["Legacy Site"]["enrollRate"] == 100        # no site status → falls back to trial


def test_not_recruiting_trial_is_not_recruiting(api):
    c = api([make_study("NCT00000002", status="ACTIVE_NOT_RECRUITING",
                        locations=[loc("Site A", None)])])
    assert c.get("/api/sites/?condition=x").json()["sites"][0]["enrollRate"] == 0


def test_sites_without_coordinates_are_still_ranked(api):
    c = api([make_study("NCT00000003", locations=[loc("Geo Hospital"),
                                                  loc("No Coordinates Clinic", lat=None, lon=None)],
                        sites=[loc("Geo Hospital")], siteCount=2)])
    names = {r["facility"] for r in c.get("/api/sites/?condition=x").json()["sites"]}
    assert names == {"Geo Hospital", "No Coordinates Clinic"}


# ── Finding 6 (+Fable): research readouts ───────────────────────────────────
def test_research_counts_only_genuinely_upcoming_readouts(api):
    soon = f"{TODAY.year + 1}-06"
    studies = [
        make_study("NCT00000010", status="RECRUITING", primaryCompletionDate=soon, primaryCompletionType="ESTIMATED"),
        make_study("NCT00000011", status="COMPLETED", primaryCompletionDate=soon, primaryCompletionType="ESTIMATED"),
        make_study("NCT00000012", status="WITHDRAWN", primaryCompletionDate=soon, primaryCompletionType="ESTIMATED"),
        make_study("NCT00000013", status="TERMINATED", primaryCompletionDate=soon, primaryCompletionType="ESTIMATED"),
        make_study("NCT00000014", status="ACTIVE_NOT_RECRUITING", primaryCompletionDate=f"{TODAY.year}-01",
                   primaryCompletionType="ACTUAL"),
        make_study("NCT00000015", status="RECRUITING", primaryCompletionDate=f"{TODAY.year + 4}-06",
                   primaryCompletionType="ESTIMATED"),                    # beyond 24 months
    ]
    d = api(studies).get("/api/research/?condition=x").json()["readoutForecast"]
    assert d["upcomingTotal"] == 1
    assert sum(y["total"] for y in d["byYear"]) == 2                      # in 5-yr chart: #10 and #15


def test_discontinuation_insight_is_suppressed_for_tiny_samples(api):
    studies = [make_study("NCT00000020", status="TERMINATED"), make_study("NCT00000021")]
    d = api(studies).get("/api/research/?condition=x").json()
    assert not [i for i in d["insights"] if i["kind"] == "risk"]


# ── Finding 7: competition demand ───────────────────────────────────────────
def test_completed_trials_do_not_inflate_competing_enrollment(api):
    studies = [
        make_study("NCT00000030", status="RECRUITING", enrollment={"count": 100, "type": "ESTIMATED"}),
        make_study("NCT00000031", status="COMPLETED", enrollment={"count": 5000, "type": "ACTUAL"}),
        make_study("NCT00000032", status="NOT_YET_RECRUITING", enrollment={"count": 50, "type": "ESTIMATED"}),
    ]
    us = next(x for x in api(studies).get("/api/landscape/geo?condition=x").json()["countries"]
              if x["country"] == "United States")
    assert us["trialCount"] == 3 and us["competingEnrollment"] == 150


def test_upcoming_readouts_list_excludes_history(api):
    studies = [
        make_study("NCT00000040", status="COMPLETED", primaryCompletionDate="1998-05", primaryCompletionType="ACTUAL"),
        make_study("NCT00000041", status="RECRUITING", primaryCompletionDate=f"{TODAY.year + 1}-03", primaryCompletionType=None),
    ]
    d = api(studies).get("/api/competition/?condition=x").json()
    assert [r["nctId"] for r in d["readouts"]] == ["NCT00000041"]
    assert d["readouts"][0]["primaryCompletionType"] is None              # not silently "Actual"


# ── Finding 9 + multi-phase ─────────────────────────────────────────────────
def test_phase_chart_counts_each_trial_once_including_phase_less(api):
    studies = [make_study("NCT00000050", phases=[]),
               make_study("NCT00000051", phases=["PHASE2", "PHASE3"]),
               make_study("NCT00000052", phases=["PHASE2"])]
    d = api(studies).get("/api/landscape/?condition=x").json()
    assert d["phaseCounts"] == {"NA": 1, "PHASE2/PHASE3": 1, "PHASE2": 1}
    assert sum(d["phaseCounts"].values()) == 3
    assert d["phaseLabels"]["PHASE2/PHASE3"] == "Phase II/III"


def test_landscape_reports_median_not_mean(api):
    sizes = [10, 20, 10000]
    studies = [make_study(f"NCT0000006{i}", enrollment={"count": n, "type": "ACTUAL"}) for i, n in enumerate(sizes)]
    assert api(studies).get("/api/landscape/?condition=x").json()["medianEnrollment"] == 20


# ── Geo: site dots are spread across countries ──────────────────────────────
def test_geo_keeps_sites_for_every_country(api):
    studies = []
    for i, country in enumerate(["United States", "Germany", "Japan", "Brazil", "India", "Kenya", "Peru", "Chile"]):
        site = loc(f"Hosp {country}", country=country, lat=10.0 + i, lon=20.0 + i)
        studies.append(make_study(f"NCT0000007{i}", countries={country: 1}, sites=[site], locations=[site]))
    d = api(studies).get("/api/landscape/geo?condition=x").json()
    assert all(len(c["sites"]) == 1 for c in d["countries"]) and len(d["countries"]) == 8


# ── Coverage / retrieval progress contract ──────────────────────────────────
def test_every_analytics_endpoint_reports_coverage(api):
    c = api([make_study()])
    for path in ["landscape/", "landscape/geo", "competition/", "research/", "sites/", "cohorts/"]:
        j = c.get(f"/api/{path}?condition=x").json()
        assert j["coverage"]["isComplete"] is True and j["coverage"]["analyzed"] == 1, path
    s = c.get("/api/datasets/status?condition=x").json()
    assert s["state"] == "complete"


# ── Cohorts false positives ─────────────────────────────────────────────────
def test_biomarker_and_regimen_false_positives(api):
    studies = [
        make_study("NCT00000080", eligibility={"criteria": "All inclusion criteria must be met. Kit provided.",
                                               "minimumAge": "18 Years", "maximumAge": "N/A"},
                   interventions=[{"type": "DRUG", "name": "Drug A"}, {"type": "DRUG", "name": "Placebo"}]),
        make_study("NCT00000081", eligibility={"criteria": "EGFR mutation required", "minimumAge": "18 Years",
                                               "maximumAge": "N/A"},
                   interventions=[{"type": "DRUG", "name": "Drug A"}, {"type": "DRUG", "name": "Drug B"}]),
    ]
    c = api(studies)
    bio = {g["key"]: g["trialCount"] for g in c.get("/api/cohorts/?condition=x&axis=biomarker").json()["groups"]}
    assert bio == {"all_comers": 1, "biomarker": 1}
    reg = {g["key"]: g["trialCount"] for g in c.get("/api/cohorts/?condition=x&axis=mono_combo").json()["groups"]}
    assert reg == {"mono": 1, "combo": 1}                                 # placebo is not a second drug


def test_cohort_query_parsing():
    from routers.cohorts import _parse_query
    assert _parse_query("Non-small cell lung cancer") == ("lung", [])
    assert _parse_query("HER2 positive breast cancer") == ("breast", ["her2"])
    assert _parse_query("AML")[0] == "myeloid"
    assert _parse_query("myelofibrosis anemia") == ("myelofibrosis", ["anemia"])


def test_competition_window_is_a_view_not_a_second_dataset(api):
    studies = [
        make_study("NCT00000090", status="RECRUITING", primaryCompletionDate=f"{TODAY.year + 1}-03", primaryCompletionType="ESTIMATED"),
        make_study("NCT00000091", status="WITHDRAWN", primaryCompletionDate=f"{TODAY.year + 1}-03", primaryCompletionType="ESTIMATED"),
        make_study("NCT00000092", status="TERMINATED", primaryCompletionDate=f"{TODAY.year + 1}-04", primaryCompletionType="ESTIMATED"),
        make_study("NCT00000093", status="COMPLETED", primaryCompletionDate=f"{TODAY.year - 1}-05", primaryCompletionType="ACTUAL"),
    ]
    c = api(studies)
    fut = c.get(f"/api/competition/?condition=x&completionFrom={TODAY.isoformat()}&completionTo={TODAY.year + 2}-12-31").json()
    assert [r["nctId"] for r in fut["readouts"]] == ["NCT00000090"]
    past = c.get(f"/api/competition/?condition=x&completionFrom={TODAY.year - 1}-01-01&completionTo={TODAY.year - 1}-12-31").json()
    assert [r["nctId"] for r in past["readouts"]] == ["NCT00000093"]
    from services import datasets
    assert len(datasets.manager._mem) == 1                    # one dataset served both windows
