def signup(client, username="alice", password="secret123"):
    return client.post(
        "/signup",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def login(client, username="alice", password="secret123"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def add_application(client, company="Google", role="Developer", status="Applied"):
    return client.post(
        "/add",
        data={
            "company": company,
            "role": role,
            "status": status,
            "applied_date": "2026-10-26",
            "notes": "",
        },
        follow_redirects=True,
    )


# ---------- Authentication ----------

def test_dashboard_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_signup_and_login(client):
    response = signup(client)
    assert b"Account created" in response.data

    response = login(client)
    assert b"My applications" in response.data


def test_duplicate_username_rejected(client):
    signup(client)
    response = signup(client)
    assert b"Username already taken" in response.data


def test_short_password_rejected(client):
    response = signup(client, password="123")
    assert b"at least 6 characters" in response.data


def test_wrong_password(client):
    signup(client)
    response = login(client, password="wrongpass")
    assert b"Wrong username or password" in response.data


def test_logout(client):
    signup(client)
    login(client)
    client.get("/logout")
    response = client.get("/")
    assert response.status_code == 302


def test_stale_session_is_handled(client):
    # Simulate a cookie for a user that no longer exists (database reset)
    with client.session_transaction() as sess:
        sess["user_id"] = 999
        sess["username"] = "ghost"
    response = client.get("/", follow_redirects=True)
    assert b"Please log in again" in response.data


# ---------- CRUD ----------

def test_add_application(client):
    signup(client)
    login(client)
    response = add_application(client)
    assert b"Application added" in response.data
    assert b"Google" in response.data


def test_add_requires_company(client):
    signup(client)
    login(client)
    response = add_application(client, company="")
    assert b"Company and role are required" in response.data


def test_edit_application(client):
    signup(client)
    login(client)
    add_application(client)
    response = client.post(
        "/edit/1",
        data={
            "company": "Microsoft",
            "role": "Developer",
            "status": "Interview",
            "applied_date": "2026-10-26",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert b"Application updated" in response.data
    assert b"Microsoft" in response.data


def test_delete_application(client):
    signup(client)
    login(client)
    add_application(client)
    response = client.post("/delete/1", follow_redirects=True)
    assert b"Application deleted" in response.data
    assert b"Google" not in response.data


# ---------- Filter ----------

def test_status_filter(client):
    signup(client)
    login(client)
    add_application(client, company="AlphaCorp", status="Applied")
    add_application(client, company="BetaCorp", status="Interview")

    response = client.get("/?status=Interview")
    assert b"BetaCorp" in response.data
    assert b"AlphaCorp" not in response.data


# ---------- Data isolation ----------

def test_users_cannot_see_or_change_each_others_data(client):
    # Alice adds an application
    signup(client, "alice", "secret123")
    login(client, "alice", "secret123")
    add_application(client, company="AliceSecretCorp")
    client.get("/logout")

    # Bob logs in and must not see it
    signup(client, "bob", "secret456")
    login(client, "bob", "secret456")
    response = client.get("/")
    assert b"AliceSecretCorp" not in response.data

    # Bob cannot open Alice's edit page
    response = client.get("/edit/1", follow_redirects=True)
    assert b"Application not found" in response.data

    # Bob cannot delete Alice's application
    client.post("/delete/1", follow_redirects=True)
    client.get("/logout")

    # Alice still has her application
    login(client, "alice", "secret123")
    response = client.get("/")
    assert b"AliceSecretCorp" in response.data

# ---------- Extra validation and edge cases ----------

def test_signup_requires_username_and_password(client):
    response = signup(client, username="", password="")
    assert b"Username and password are required" in response.data


def test_add_rejects_invalid_status(client):
    signup(client)
    login(client)
    response = add_application(client, status="Hacked")
    assert b"Invalid status" in response.data


def test_edit_page_loads(client):
    signup(client)
    login(client)
    add_application(client, company="Google")
    response = client.get("/edit/1")
    assert response.status_code == 200
    assert b"Google" in response.data


def test_edit_requires_company_and_role(client):
    signup(client)
    login(client)
    add_application(client)
    response = client.post(
        "/edit/1",
        data={"company": "", "role": "", "status": "Applied",
              "applied_date": "", "notes": ""},
        follow_redirects=True,
    )
    assert b"Company and role are required" in response.data


def test_edit_rejects_invalid_status(client):
    signup(client)
    login(client)
    add_application(client)
    response = client.post(
        "/edit/1",
        data={"company": "Google", "role": "Developer", "status": "Hacked",
              "applied_date": "", "notes": ""},
        follow_redirects=True,
    )
    assert b"Invalid status" in response.data