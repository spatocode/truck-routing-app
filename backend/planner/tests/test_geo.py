from planner.geo import LatLon, haversine_miles, sample_along_path


def test_haversine_chicago_to_st_louis_is_about_260_miles():
    chicago = LatLon(41.8781, -87.6298)
    st_louis = LatLon(38.6270, -90.1994)
    miles = haversine_miles(chicago, st_louis)
    assert 250 < miles < 270


def test_samples_include_origin_interval_points_and_destination():
    start = LatLon(40.0, -90.0)
    end = LatLon(40.0, -88.0)
    points = [start, end]
    samples = sample_along_path(points, 50)
    miles = [mile for _point, mile in samples]
    assert miles[0] == 0
    assert any(abs(mile - 50) < 1 for mile in miles)
    assert miles[-1] > 90
