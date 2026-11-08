import pytest
from fastapi.testclient import TestClient
from ottomate_core.testing import FakeDatabase, use_database, use_users_database, use_organizers
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "1")
    use_database(monkeypatch, FakeDatabase(id_prefix="game"))
    use_users_database(monkeypatch, FakeDatabase(id_prefix="users"))
    use_organizers(monkeypatch, ["admin@example.com"])
    return TestClient(app)


def auth_headers(email: str = "player1@example.com") -> dict[str, str]:
    return {"Authorization": f"Bearer dev:{email}"}


def test_create_pve_match(client):
    res = client.post(
        "/api/matches",
        headers=auth_headers("alice@example.com"),
        json={
            "title": "Alice vs Bot",
            "mode": "pve",
            "bot_difficulty": "medium",
        },
    )
    assert res.status_code == 201
    match = res.json()["match"]
    assert match["title"] == "Alice vs Bot"
    assert match["player1_email"] == "alice@example.com"
    assert match["player2_ready"] is True  # Bot is pre-deployed
    assert match["status"] == "setup"


def test_pvp_match_lifecycle_and_fog_of_war(client):
    # 1. Alice creates PvP match
    res = client.post(
        "/api/matches",
        headers=auth_headers("alice@example.com"),
        json={
            "title": "Naval Showdown",
            "mode": "pvp",
        },
    )
    assert res.status_code == 201
    match_id = res.json()["match"]["id"]

    # 2. Bob joins the match
    join_res = client.post(
        f"/api/matches/{match_id}/join",
        headers=auth_headers("bob@example.com"),
    )
    assert join_res.status_code == 200

    # 3. Alice deploys fleet
    alice_fleet = [
        {"ship_id": "carrier", "row": 0, "col": 0, "orientation": "horizontal"},  # A1-E1
        {"ship_id": "battleship", "row": 1, "col": 0, "orientation": "horizontal"},  # A2-D2
        {"ship_id": "cruiser", "row": 2, "col": 0, "orientation": "horizontal"},  # A3-C3
        {"ship_id": "submarine", "row": 3, "col": 0, "orientation": "horizontal"},  # A4-C4
        {"ship_id": "destroyer", "row": 4, "col": 0, "orientation": "horizontal"},  # A5-B5
    ]
    deploy_res = client.post(
        f"/api/matches/{match_id}/deploy",
        headers=auth_headers("alice@example.com"),
        json={"ships": alice_fleet},
    )
    assert deploy_res.status_code == 200
    assert deploy_res.json()["ready"] is True

    # 4. Bob deploys fleet -> triggers battle start!
    bob_fleet = [
        {"ship_id": "carrier", "row": 5, "col": 0, "orientation": "horizontal"},  # A6-E6
        {"ship_id": "battleship", "row": 6, "col": 0, "orientation": "horizontal"},  # A7-D7
        {"ship_id": "cruiser", "row": 7, "col": 0, "orientation": "horizontal"},  # A8-C8
        {"ship_id": "submarine", "row": 8, "col": 0, "orientation": "horizontal"},  # A9-C9
        {"ship_id": "destroyer", "row": 9, "col": 0, "orientation": "horizontal"},  # A10-B10
    ]
    bob_deploy_res = client.post(
        f"/api/matches/{match_id}/deploy",
        headers=auth_headers("bob@example.com"),
        json={"ships": bob_fleet},
    )
    assert bob_deploy_res.status_code == 200
    assert bob_deploy_res.json()["status"] == "in_progress"
    assert bob_deploy_res.json()["turn_player"] == "alice@example.com"

    # 5. Check Fog of War Snapshot for Alice
    snapshot_res = client.get(
        f"/api/matches/{match_id}",
        headers=auth_headers("alice@example.com"),
    )
    assert snapshot_res.status_code == 200
    snap = snapshot_res.json()
    assert snap["is_my_turn"] is True
    # Alice can see her own ships
    assert "carrier" in snap["my_board"]["ships"]
    # Alice CANNOT see Bob's un-hit ships!
    assert "ships" not in snap["radar_board"]

    # 6. Alice fires and hits Bob's Destroyer at A10!
    hit_res = client.post(
        f"/api/matches/{match_id}/fire",
        headers=auth_headers("alice@example.com"),
        json={"coordinate": "A10"},
    )
    assert hit_res.status_code == 200
    hit_data = hit_res.json()
    assert hit_data["shot"]["result"] == "hit"
    assert hit_data["shot"]["turn_continues"] is True
    # Streak on hit: Alice's turn continues!
    assert hit_data["turn_player"] == "alice@example.com"

    # 7. Alice fires again and sinks Bob's Destroyer at B10!
    sink_res = client.post(
        f"/api/matches/{match_id}/fire",
        headers=auth_headers("alice@example.com"),
        json={"coordinate": "B10"},
    )
    assert sink_res.status_code == 200
    sink_data = sink_res.json()
    assert sink_data["shot"]["result"] == "hit"
    assert sink_data["shot"]["sunk"] is True
    assert sink_data["shot"]["ship_name"] == "Destroyer"
    assert sink_data["turn_player"] == "alice@example.com"

    # 8. Alice misses at J1
    miss_res = client.post(
        f"/api/matches/{match_id}/fire",
        headers=auth_headers("alice@example.com"),
        json={"coordinate": "J1"},
    )
    assert miss_res.status_code == 200
    miss_data = miss_res.json()
    assert miss_data["shot"]["result"] == "miss"
    # Miss switches turn to Bob!
    assert miss_data["turn_player"] == "bob@example.com"

    # 9. Bob surrenders
    surrender_res = client.post(
        f"/api/matches/{match_id}/surrender",
        headers=auth_headers("bob@example.com"),
    )
    assert surrender_res.status_code == 200
    assert surrender_res.json()["winner"] == "alice@example.com"


def test_user_stats(client):
    # Verify stats endpoint returns zeros initially
    res = client.get("/api/me/stats", headers=auth_headers("newbie@example.com"))
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] == 0
    assert data["accuracy_pct"] == 0.0
