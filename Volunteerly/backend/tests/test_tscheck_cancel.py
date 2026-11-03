"""Criterion: Smart Cancellation Manager ranking (seeded Rohan Gowda vacancy on Food Drive)."""


def login_ngo(client):
    r = client.post("/auth/login", json={"email": "annapurna@demo.vc", "password": "Demo@1234"})
    assert r.status_code == 200, r.text


def test_cancellations_shows_seeded_vacancy_and_ranked_candidates(client):
    login_ngo(client)
    r = client.get("/ngo/cancellations")
    assert r.status_code == 200, r.text
    data = r.json()
    rohan_vac = [v for v in data["vacancies"] if v["cancelled_volunteer_name"] == "Rohan Gowda"]
    assert rohan_vac, f"expected seeded Rohan Gowda vacancy, got: {[v['cancelled_volunteer_name'] for v in data['vacancies']]}"
    vac = rohan_vac[0]
    assert vac["last_minute"] is True or vac["shift"]["start_time"] == "11:00"

    cands = client.get(f"/ngo/shifts/{vac['shift']['id']}/candidates",
                       params={"registration_id": vac["cancelled_registration_id"]})
    assert cands.status_code == 200, cands.text
    cdata = cands.json()
    names = [c["volunteer"]["name"] for c in cdata["candidates"]]
    assert "Kavya Reddy" in names, names
    scores = [c["score"] for c in cdata["candidates"]]
    assert scores == sorted(scores, reverse=True), "candidates must be ranked descending by score"
    kavya = next(c for c in cdata["candidates"] if c["volunteer"]["name"] == "Kavya Reddy")
    assert kavya["score"] == max(scores), "Kavya Reddy expected to rank #1"
    assert kavya["score"] >= 95

    # excluded: Aditya Menon (opted out) and Sanjay (outside radius) must never be listed
    assert "Aditya Menon" not in names
    assert "Sanjay" not in " ".join(names)
    assert cdata["excluded"], "expected non-empty excluded reasons breakdown"
