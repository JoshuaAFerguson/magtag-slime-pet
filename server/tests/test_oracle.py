from app.oracle import build


def test_build_shapes_payload():
    weather = {"tags": ["extreme_heat"], "temp_c": 43, "code": 0, "sunset_soon": False}
    mooninfo = {"phase": 4, "name": "full", "illum": 0.98}
    out = build(weather, mooninfo, ts=1718900000)
    assert out["weather"]["tags"] == ["extreme_heat"]
    assert out["moon"]["phase"] == 4
    assert out["ts"] == 1718900000
