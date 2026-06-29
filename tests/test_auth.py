from backend.factory import create_app


def test_registration_password_policy_and_login(isolated_database):
    app = create_app(load_artifacts=False)
    app.config.update(TESTING=True)
    client = app.test_client()

    weak = client.post("/api/register", json={"username": "bob", "password": "weak"})
    assert weak.status_code == 400

    registered = client.post("/api/register", json={"username": "bob", "password": "StrongPass1"})
    assert registered.status_code == 200

    client.post("/api/logout")
    logged_in = client.post("/api/login", json={"username": "bob", "password": "StrongPass1"})
    assert logged_in.status_code == 200
    assert logged_in.get_json()["authenticated"] is True


def test_admin_endpoint_requires_session(isolated_database):
    app = create_app(load_artifacts=False)
    app.config.update(TESTING=True)
    client = app.test_client()

    assert client.get("/api/admin/transactions").status_code == 401
