from types import SimpleNamespace

import pytest

from app.api.jobs import get_retouch_advice
from app.core.errors import ApiError
from app.orchestration.retouch_advice import convert_post_advice


def convert(source):
    return convert_post_advice(source, job_id="job_test", media_id="media_test", result_id="result_test")


def test_shadow_direction_and_no_substitution():
    source = {"Highlights2012": -40, "Shadows2012": -10, "Blacks2012": -20,
              "Contrast2012": 8, "Saturation": -22, "Vibrance": -10, "Clarity2012": 15, "Dehaze": 8}
    result = convert(source)
    assert result["params"] == {"highlights": -.4, "shadows": -.1, "contrast": .08,
                                "saturation": -.22, "vibrance": -.1, "clarity": .15}
    assert {r["parameter"] for r in result["skipped"]} == {"Blacks2012", "Dehaze"}
    assert source["Shadows2012"] == -10
    assert all(r["approximate"] for r in result["converted"])


@pytest.mark.parametrize("raw", [True, "-10", "-10 ~ -20", float("nan"), float("inf"), -101, None])
def test_invalid_values_not_guessed(raw):
    result = convert({"Shadows2012": raw})
    assert result["params"] == {} and len(result["skipped"]) == 1


def test_neutral_direction_and_explicit_limits():
    for v in [-100, -10, 0, 10, 100]:
        result = convert({"Shadows2012": v})
        actual = result["params"]["shadows"]
        assert (actual > 0) == (v > 0) and (actual < 0) == (v < 0)
        assert abs(actual) <= .35
        assert result["converted"][0]["clamped"] == (abs(v) > 35)
    assert convert({"Exposure2012": -.2, "Temperature": 5000, "Dehaze": 8})["params"] == {}


def stores(media_ids=None, status="succeeded", payload=None):
    job = SimpleNamespace(media_ids=media_ids or ["media_test"])
    post = SimpleNamespace(agent="post", status=status, id="result_test", payload=payload or {"xmp_params": {"Shadows2012": -10}})
    return SimpleNamespace(get=lambda _: job), SimpleNamespace(list_latest_by_job=lambda _: [post])


def test_saved_result_provenance():
    jobs, results = stores()
    result = get_retouch_advice("job_test", "media_test", jobs, results)
    assert result["source_result_id"] == "result_test"
    assert result["params"]["shadows"] == -.1


@pytest.mark.parametrize("ids,status,payload", [(["other"], "succeeded", None),
    (["media_test", "other"], "succeeded", None), (["media_test"], "failed", None),
    (["media_test"], "succeeded", {"adjustments": ["提亮一些"]})])
def test_wrong_photo_batch_failed_or_unstructured_refused(ids, status, payload):
    jobs, results = stores(ids, status, payload)
    with pytest.raises(ApiError):
        get_retouch_advice("job_test", "media_test", jobs, results)
