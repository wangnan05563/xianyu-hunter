from xianyu_hunter.web.app import app


def _route_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_stats_routes_keep_public_api_prefix_once() -> None:
    paths = _route_paths()

    assert "/api/stats" in paths
    assert "/api/events/recent" in paths
    assert "/api/stats/today" in paths
    assert "/api/stats/trend" in paths
    assert "/api/stats/business-kpi" in paths
    assert "/api/stats/seller-price-trend" in paths


def test_stats_routes_do_not_register_double_api_prefix() -> None:
    paths = _route_paths()

    assert "/api/api/stats" not in paths
    assert "/api/api/events/recent" not in paths
