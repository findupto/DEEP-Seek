import pytest

import enterprise_backend as backend


def test_api_requires_authentication_by_default():
    if backend.FastAPI is None:
        pytest.skip("enterprise dependencies are not installed")
    if backend.ALLOW_ANONYMOUS:
        pytest.skip("anonymous mode explicitly enabled")
    if not backend.API_TOKEN:
        with pytest.raises(backend.HTTPException) as exc:
            backend.auth(None)
        assert exc.value.status_code == 503
    else:
        with pytest.raises(backend.HTTPException) as exc:
            backend.auth("wrong-token")
        assert exc.value.status_code == 401


def test_gps_model_validates_coordinates():
    if backend.FastAPI is None:
        pytest.skip("enterprise dependencies are not installed")
    item = backend.GPSItem(rider_id="r1", lat=31.0, lon=71.0, accuracy=10)
    assert item.rider_id == "r1"
    with pytest.raises(Exception):
        backend.GPSItem(rider_id="r1", lat=91, lon=71)
