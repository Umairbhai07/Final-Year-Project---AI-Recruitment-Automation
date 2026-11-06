import re

from app.core.security import hash_password, pwd_context
from tests.conftest import register


def test_register_login_me(client):
    headers = register(client, "Mixed@Case.com", "candidate", name="Ali")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "mixed@case.com" and body["role"] == "candidate"
    assert "password_hash" not in body


def test_register_duplicate_email_409(client):
    register(client, "a@test.com", "candidate")
    r = client.post(
        "/api/auth/register",
        json={"full_name": "X Y", "email": "A@test.com", "password": "Passw0rd!", "role": "recruiter"},
    )
    assert r.status_code == 409


def test_password_rules(client):
    base = {"full_name": "X Y", "email": "p@test.com", "role": "candidate"}
    assert client.post("/api/auth/register", json={**base, "password": "short1"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "password": "longenoughnonumber"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "password": "longenough1"}).status_code == 201


def test_invalid_role_and_email(client):
    r = client.post(
        "/api/auth/register", json={"full_name": "X Y", "email": "bad", "password": "Passw0rd!", "role": "candidate"}
    )
    assert r.status_code == 422
    r = client.post(
        "/api/auth/register", json={"full_name": "X Y", "email": "x@test.com", "password": "Passw0rd!", "role": "admin"}
    )
    assert r.status_code == 422


def test_wrong_password_401(client):
    register(client, "w@test.com", "candidate")
    r = client.post("/api/auth/login", json={"email": "w@test.com", "password": "wrong1234"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


def test_unauthenticated_and_bad_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_refresh_rotates_and_old_token_is_revoked(client):
    register(client, "r@test.com", "candidate")
    login = client.post("/api/auth/login", json={"email": "r@test.com", "password": "Passw0rd!"}).json()
    r = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["refresh_token"] != login["refresh_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {new['access_token']}"}).status_code == 200
    # old refresh token no longer works
    assert client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401


def test_logout_revokes_refresh(client):
    register(client, "l@test.com", "candidate")
    login = client.post("/api/auth/login", json={"email": "l@test.com", "password": "Passw0rd!"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert (
        client.post("/api/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers).status_code
        == 204
    )
    assert client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401


def test_login_lockout_after_10_failures(client):
    register(client, "lock@test.com", "candidate")
    for _ in range(10):
        assert (
            client.post("/api/auth/login", json={"email": "lock@test.com", "password": "bad12345"}).status_code == 401
        )
    r = client.post("/api/auth/login", json={"email": "lock@test.com", "password": "Passw0rd!"})
    assert r.status_code == 429
    # a different IP is not blocked
    r = client.post(
        "/api/auth/login",
        json={"email": "lock@test.com", "password": "Passw0rd!"},
        headers={"X-Forwarded-For": "10.0.0.9"},
    )
    assert r.status_code == 200


def test_password_is_bcrypt_hashed():
    h = hash_password("Secret123")
    assert h.startswith("$2b$") and pwd_context.verify("Secret123", h)


def test_login_with_portal_role(client):
    register(client, "portal@test.com", "candidate")
    ok = client.post("/api/auth/login", json={"email": "portal@test.com", "password": "Passw0rd!", "role": "candidate"})
    assert ok.status_code == 200
    r = client.post("/api/auth/login", json={"email": "portal@test.com", "password": "Passw0rd!", "role": "recruiter"})
    assert r.status_code == 403 and "candidate account" in r.json()["detail"]


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _code(mail: dict) -> str:
    return re.search(r"code: (\d{6})", mail["subject"]).group(1)


def test_forgot_and_reset_password_with_code(client, emails):
    register(client, "reset@test.com", "candidate")
    emails.clear()  # the welcome email asking to confirm the address
    old_refresh = _login(client, "reset@test.com", "Passw0rd!").json()["refresh_token"]

    # same answer for unknown emails, and no email is sent
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@test.com"})
    assert r.status_code == 202 and not emails
    r = client.post("/api/auth/forgot-password", json={"email": "RESET@test.com"})
    assert r.status_code == 202 and len(emails) == 1 and emails[0]["to"] == "reset@test.com"
    code = _code(emails[0])
    assert code in emails[0]["html"]

    url = "/api/auth/reset-password-code"
    body = {"email": "reset@test.com", "code": code, "password": "NewPass123"}
    assert client.post(url, json={**body, "password": "nonumber"}).status_code == 422
    assert client.post(url, json={**body, "code": "12ab56"}).status_code == 422
    wrong = "000000" if code != "000000" else "111111"
    assert client.post(url, json={**body, "code": wrong}).status_code == 400
    assert client.post(url, json={**body, "email": "nobody@test.com"}).status_code == 400
    assert client.post(url, json=body).status_code == 204
    assert _login(client, "reset@test.com", "Passw0rd!").status_code == 401
    assert _login(client, "reset@test.com", "NewPass123").status_code == 200
    # the code works once, and old sessions are signed out
    assert client.post(url, json={**body, "password": "Other1234"}).status_code == 400
    assert client.post("/api/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401


def test_wrong_codes_are_limited(client, emails):
    register(client, "guess@test.com", "candidate")
    client.post("/api/auth/forgot-password", json={"email": "guess@test.com"})
    code = _code(emails[-1])
    wrong = [f"{(int(code) + i) % 1_000_000:06d}" for i in range(1, 6)]
    url = "/api/auth/reset-password-code"
    for w in wrong:
        assert (
            client.post(url, json={"email": "guess@test.com", "code": w, "password": "NewPass123"}).status_code == 400
        )
    # even the right code is refused now
    r = client.post(url, json={"email": "guess@test.com", "code": code, "password": "NewPass123"})
    assert r.status_code == 429


def test_code_expires_after_two_windows():
    from app.core import security

    now = 1_000_000_000.0
    c = security.create_code("u1", "reset", "hash", now)
    assert security.code_matches(c, "u1", "reset", "hash", now + security.CODE_WINDOW_SECONDS)
    assert not security.code_matches(c, "u1", "reset", "hash", now + 2 * security.CODE_WINDOW_SECONDS)
    assert not security.code_matches(c, "u1", "change", "hash", now)  # a reset code can't change the password
    assert not security.code_matches(c, "u1", "reset", "other-hash", now)


def test_change_password_with_email_code(client, emails):
    headers = register(client, "change@test.com", "recruiter")
    send = "/api/auth/change-password/send-code"
    url = "/api/auth/change-password"
    assert client.post(send, json={"current_password": "x"}).status_code == 401
    emails.clear()
    assert client.post(send, json={"current_password": "wrong"}, headers=headers).status_code == 400
    assert not emails
    assert client.post(send, json={"current_password": "Passw0rd!"}, headers=headers).status_code == 202
    code = _code(emails[-1])
    wrong = "000000" if code != "000000" else "111111"
    assert client.post(url, json={"code": wrong, "new_password": "NewPass123"}, headers=headers).status_code == 400
    same = {"code": code, "new_password": "Passw0rd!"}
    assert client.post(url, json=same, headers=headers).status_code == 400
    ok = {"code": code, "new_password": "NewPass123"}
    assert client.post(url, json=ok, headers=headers).status_code == 204
    assert _login(client, "change@test.com", "NewPass123").status_code == 200
    # a reset code from "forgot password" is not accepted here
    client.post("/api/auth/forgot-password", json={"email": "change@test.com"})
    headers = {"Authorization": "Bearer " + _login(client, "change@test.com", "NewPass123").json()["access_token"]}
    r = client.post(url, json={"code": _code(emails[-1]), "new_password": "Third1234"}, headers=headers)
    assert r.status_code == 400
