"""The demo candidates script: complete profiles that can sign in and apply."""

from app.models import User
from scripts.seed_candidates import CANDIDATES, PASSWORD, seed_candidates


def test_demo_candidates_can_sign_in_and_apply(client, db, job):
    seed_candidates()
    seed_candidates()  # running it again skips existing accounts
    assert db.query(User).filter(User.email.like("%@demo.com")).count() == len(CANDIDATES) == 8

    r = client.post("/api/auth/login", json={"email": "ali.hassan@demo.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/profile/me", headers=h).json()
    assert me["complete"] and me["photo_url"] and me["has_resume"]
    r = client.post(f"/api/jobs/{job['id']}/apply", data={"answers": "{}"}, headers=h)
    assert r.status_code == 201, r.text

    seed_candidates(reset=True)
    assert db.query(User).filter(User.email.like("%@demo.com")).count() == 8
