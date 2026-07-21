from app.services.health_service import build_health_payload


def test_build_health_payload_has_expected_keys(monkeypatch) -> None:
    monkeypatch.setattr("app.services.health_service.check_database_connection", lambda: True)

    payload = build_health_payload()

    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    assert "service" in payload
    assert "environment" in payload
