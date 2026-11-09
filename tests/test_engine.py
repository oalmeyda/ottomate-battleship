import pytest
from app.engine.domain import (
    FLEET_SPECS,
    parse_coordinate,
    format_coordinate,
    ShipPlacement,
    validate_fleet_placement,
    generate_random_fleet,
    BoardState,
)
from app.engine.bot import decide_bot_shot


def test_coordinate_parsing_and_formatting():
    assert parse_coordinate("A1") == (0, 0)
    assert parse_coordinate("j10") == (9, 9)
    assert parse_coordinate("e5") == (4, 4)
    assert format_coordinate(0, 0) == "A1"
    assert format_coordinate(9, 9) == "J10"
    assert format_coordinate(4, 4) == "E5"

    with pytest.raises(ValueError):
        parse_coordinate("K1")
    with pytest.raises(ValueError):
        parse_coordinate("A0")
    with pytest.raises(ValueError):
        parse_coordinate("A11")
    with pytest.raises(ValueError):
        parse_coordinate("INVALID")


def test_ship_placement_and_validation():
    p = ShipPlacement(ship_id="destroyer", row=0, col=0, orientation="horizontal")
    assert p.occupied_coordinates() == ["A1", "B1"]

    p_vert = ShipPlacement(ship_id="cruiser", row=0, col=0, orientation="vertical")
    assert p_vert.occupied_coordinates() == ["A1", "A2", "A3"]

    # Out of bounds
    with pytest.raises(ValueError):
        ShipPlacement(ship_id="carrier", row=0, col=8, orientation="horizontal").occupied_coordinates()


def test_random_fleet_generation_and_validation():
    fleet = generate_random_fleet()
    assert len(fleet) == 5

    coords_map = validate_fleet_placement(fleet)
    assert set(coords_map.keys()) == set(FLEET_SPECS.keys())

    all_cells = [cell for cells in coords_map.values() for cell in cells]
    assert len(all_cells) == 17
    assert len(set(all_cells)) == 17  # No overlap


def test_board_shooting_and_streak_on_hit():
    fleet = [
        {"ship_id": "carrier", "row": 0, "col": 0, "orientation": "horizontal"},  # A1, B1, C1, D1, E1
        {"ship_id": "battleship", "row": 1, "col": 0, "orientation": "horizontal"},  # A2, B2, C2, D2
        {"ship_id": "cruiser", "row": 2, "col": 0, "orientation": "horizontal"},  # A3, B3, C3
        {"ship_id": "submarine", "row": 3, "col": 0, "orientation": "horizontal"},  # A4, B4, C4
        {"ship_id": "destroyer", "row": 4, "col": 0, "orientation": "horizontal"},  # A5, B5
    ]
    coords_map = validate_fleet_placement(fleet)
    board = BoardState(player_email="player@example.com", ships=coords_map)

    # Miss shot
    miss_res = board.fire_shot("J10")
    assert miss_res.result == "miss"
    assert miss_res.turn_continues is False
    assert not miss_res.sunk

    # Hit shot
    hit_res = board.fire_shot("A5")
    assert hit_res.result == "hit"
    assert hit_res.ship_id == "destroyer"
    assert hit_res.turn_continues is True  # Streak on hit!
    assert not hit_res.sunk

    # Second hit on destroyer sinks it
    sink_res = board.fire_shot("B5")
    assert sink_res.result == "hit"
    assert sink_res.sunk is True
    assert sink_res.ship_name == "Destroyer"
    assert sink_res.turn_continues is True
    assert not sink_res.game_over
    assert "destroyer" in board.sunk_ships

    # Repeat shot raises error
    with pytest.raises(ValueError):
        board.fire_shot("A5")


def test_fog_of_war_masking():
    fleet = generate_random_fleet()
    coords_map = validate_fleet_placement(fleet)
    board = BoardState(player_email="secret@example.com", ships=coords_map)

    masked = board.mask_for_opponent()
    assert "ships" not in masked
    assert masked["player_email"] == "secret@example.com"
    assert masked["shots_received"] == {}

    full = board.reveal_full()
    assert "ships" in full
    assert len(full["ships"]) == 5


def test_bot_shot_selection():
    shots_received = {
        "A1": {"result": "hit", "ship_id": "destroyer"},
    }
    sunk_ships = []

    # Medium bot should target neighbors of A1 (B1, A2)
    next_shot = decide_bot_shot(shots_received, sunk_ships, difficulty="medium")
    assert next_shot in ["B1", "A2"]

    # Hard bot should also execute without error
    hard_shot = decide_bot_shot(shots_received, sunk_ships, difficulty="hard")
    assert hard_shot in ["B1", "A2"]

    # Easy bot picks any unfired
    easy_shot = decide_bot_shot(shots_received, sunk_ships, difficulty="easy")
    assert easy_shot != "A1"


def test_shot_streaks_calculation(monkeypatch):
    from ottomate_core.testing import FakeDatabase, use_users_database
    use_users_database(monkeypatch, FakeDatabase(id_prefix="users"))
    from app.engine.stats import compute_leaderboard_and_stats

    # Match where human hits 3 times in a row, misses once, hits once
    mock_match = {
        "id": "m1",
        "status": "completed",
        "winner_email": "ace@example.com",
        "player1_email": "ace@example.com",
        "player2_email": "target@example.com",
        "mode": "pvp",
        "completed_at": "2026-11-09T00:00:00Z",
        "history": [
            {"player_email": "ace@example.com", "result": "hit", "sunk": False},
            {"player_email": "ace@example.com", "result": "hit", "sunk": False},
            {"player_email": "ace@example.com", "result": "hit", "sunk": False},
            {"player_email": "ace@example.com", "result": "miss", "sunk": False},
            {"player_email": "target@example.com", "result": "miss", "sunk": False},
            {"player_email": "ace@example.com", "result": "hit", "sunk": True},
        ],
        "player1_board": {"sunk_ships": []},
        "player2_board": {"sunk_ships": ["destroyer"]},
    }

    lb, stats_map = compute_leaderboard_and_stats([mock_match], scope="all")
    ace_stats = stats_map["ace@example.com"]
    assert ace_stats["longest_hit_streak"] == 3
    assert ace_stats["current_hit_streak"] == 1
    assert ace_stats["longest_miss_streak"] == 1
    assert ace_stats["current_miss_streak"] == 0

    target_stats = stats_map["target@example.com"]
    assert target_stats["longest_hit_streak"] == 0
    assert target_stats["current_hit_streak"] == 0
    assert target_stats["longest_miss_streak"] == 1
    assert target_stats["current_miss_streak"] == 1
