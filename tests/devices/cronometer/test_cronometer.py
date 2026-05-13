import math
from datetime import datetime
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

import wearipedia
from wearipedia.devices.cronometer import cronometer_fetch


@pytest.mark.parametrize("real", [True, False])
def test_cronometer(real):

    start_dates = [
        np.datetime64("2009-11-15"),
        np.datetime64("2021-04-01"),
        np.datetime64("2022-06-10"),
    ]
    end_dates = [
        np.datetime64("2010-02-01"),
        np.datetime64("2021-06-20"),
        np.datetime64("2022-12-10"),
    ]

    for start_date, end_date in zip(start_dates, end_dates):

        device = wearipedia.get_device(
            "cronometer/cronometer",
            start_date=np.datetime_as_string(start_date, unit="D"),
            end_date=np.datetime_as_string(end_date, unit="D"),
        )

        params = {"start_date": str(start_date), "end_date": str(end_date)}
        """
        if real:
            wearipedia._authenticate_device("cronometer/cronometer", device)
        """
        dailySummary = device.get_data("dailySummary", params=params)
        servings = device.get_data("servings", params=params)
        exercises = device.get_data("exercises", params=params)
        biometrics = device.get_data("biometrics", params=params)
        recipes = device.get_data("recipes", params=params)
        saved_meals = device.get_data("saved_meals", params=params)
        foods_with_components = device.get_data(
            "foods_with_components", params=params
        )

        daily_summary_helper(dailySummary)
        servings_helper(servings)
        exercises_helper(exercises)
        biometrics_helper(biometrics)
        recipes_helper(recipes)
        saved_meals_helper(saved_meals)
        foods_with_components_helper(foods_with_components)


valid_bounds = {
    "Energy (kcal)": (0, 7500),
    "Alcohol (g)": (0, 100),
    "Caffeine (mg)": (0, 1000),
    "Water (g)": (0, 10000),
    "B1 (Thiamine) (mg)": (0, 100),
    "B2 (Riboflavin) (mg)": (0, 100),
    "B3 (Niacin) (mg)": (0, 100),
    "B5 (Pantothenic Acid) (mg)": (0, 100),
    "B6 (Pyridoxine) (mg)": (0, 100),
    "B12 (Cobalamin) (µg)": (0, 10000),
    "Folate (µg)": (0, 1000),
    "Vitamin A (µg)": (0, 10000),
    "Vitamin C (mg)": (0, 10000),
    "Vitamin D (IU)": (0, 10000),
    "Vitamin E (mg)": (0, 100),
    "Vitamin K (µg)": (0, 1000),
    "Calcium (mg)": (0, 10000),
    "Copper (mg)": (0, 100),
    "Iron (mg)": (0, 100),
    "Magnesium (mg)": (0, 1000),
    "Manganese (mg)": (0, 100),
    "Phosphorus (mg)": (0, 10000),
    "Potassium (mg)": (0, 10000),
    "Selenium (µg)": (0, 100),
    "Sodium (mg)": (0, 10000),
    "Zinc (mg)": (0, 100),
    "Carbs (g)": (0, 1000),
    "Fiber (g)": (0, 100),
    "Starch (g)": (0, 1000),
    "Sugars (g)": (0, 1000),
    "Net Carbs (g)": (0, 1000),
    "Fat (g)": (0, 1000),
    "Cholesterol (mg)": (0, 1000),
    "Monounsaturated (g)": (0, 1000),
    "Polyunsaturated (g)": (0, 1000),
    "Saturated (g)": (0, 1000),
    "Trans-Fats (g)": (0, 1000),
    "Omega-3 (g)": (0, 1000),
    "Omega-6 (g)": (0, 1000),
    "Cystine (g)": (0, 1000),
    "Histidine (g)": (0, 1000),
    "Isoleucine (g)": (0, 1000),
    "Leucine (g)": (0, 1000),
    "Lysine (g)": (0, 1000),
    "Methionine (g)": (0, 1000),
    "Phenylalanine (g)": (0, 1000),
    "Threonine (g)": (0, 1000),
    "Tryptophan (g)": (0, 1000),
    "Tyrosine (g)": (0, 1000),
    "Valine (g)": (0, 1000),
}


def nutriton_checker(d):
    for key, bounds in valid_bounds.items():
        if not math.isnan(d[key]):
            assert d[key] >= bounds[0]
            assert d[key] < bounds[1]


def daily_summary_helper(data):
    for d in data:
        assert isinstance(d["Day"], str)
        nutriton_checker(d)
        assert isinstance(d["Completed"], bool)


def servings_helper(data):
    for d in data:
        assert isinstance(d["Day"], str)
        nutriton_checker(d)
        # The recipe-explosion pipeline in ibs-cronometer matches servings
        # to composites by food_id; the synthetic generator must surface
        # one on every row.
        assert "food_id" in d
        assert isinstance(d["food_id"], int)


def recipes_helper(data):
    assert isinstance(data, list)
    for r in data:
        assert isinstance(r["recipe_id"], int)
        assert isinstance(r["name"], str)
        assert isinstance(r["servings_per_recipe"], (int, float))
        assert isinstance(r["ingredients"], list)
        for ing in r["ingredients"]:
            assert isinstance(ing["food_id"], int)
            assert isinstance(ing["name"], str)
            assert isinstance(ing["amount"], (int, float))
            assert isinstance(ing["unit"], str)
            assert isinstance(ing["fraction_of_recipe"], (int, float))


def saved_meals_helper(data):
    assert isinstance(data, list)
    for m in data:
        assert isinstance(m["meal_id"], int)
        assert isinstance(m["name"], str)
        assert isinstance(m["servings"], list)
        for s in m["servings"]:
            assert isinstance(s["food_id"], int)
            assert isinstance(s["name"], str)
            assert isinstance(s["amount"], (int, float))
            assert isinstance(s["unit"], str)


def foods_with_components_helper(data):
    assert isinstance(data, dict)
    for fid, components in data.items():
        assert isinstance(fid, int)
        assert isinstance(components, list)


def exercises_helper(data):
    for d in data:
        assert isinstance(d["Day"], str)
        assert isinstance(d["Exercise"], str)
        assert isinstance(d["Minutes"], float)
        assert isinstance(d["Calories Burned"], float)
        assert d["Minutes"] >= 0
        assert d["Calories Burned"] <= 0


def biometrics_helper(data):
    for d in data:
        assert isinstance(d["Day"], str)
        assert isinstance(d["Metric"], str)
        assert isinstance(d["Unit"], str)
        assert isinstance(d["Amount"], (float, int))
        assert d["Amount"] >= 0


def _make_mock_session(json_payload=None):
    """Build a MagicMock that mimics a `requests.Session` well enough for
    `cronometer_fetch`'s recipe / saved-meal / components fetchers."""
    session = MagicMock()

    auth_response = MagicMock()
    auth_response.status_code = 200
    auth_response.text = '//OK[12345,1,2,3]'
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.text = '//OK["fake-auth-token",1,2,3]'
    session.post.side_effect = [auth_response, token_response]

    cookies = MagicMock()
    cookies.get.return_value = "nonce-cookie-value"
    session.cookies = cookies

    get_response = MagicMock()
    get_response.status_code = 200
    get_response.json.return_value = json_payload if json_payload is not None else []
    get_response.text = '{"ok": true}'
    session.get.return_value = get_response

    # Any other HTTP verb is a contract violation; make it noisy.
    for verb in ("put", "patch", "delete", "options", "head"):
        getattr(session, verb).side_effect = AssertionError(
            f"recipe / saved-meal fetchers must not call session.{verb}"
        )
    return session


def test_recipe_fetchers_are_read_only():
    """Hard guardrail required by `explode-plan.md` section 4: the
    recipes / saved-meals / foods-with-components fetchers must never
    issue a non-GET request to a user-diary endpoint, and must never
    touch a URL whose path contains 'explode', 'delete', or 'update'.
    """

    forbidden = ("explode", "delete", "update")

    for data_type, json_payload in [
        ("recipes", [{"recipe_id": 1, "name": "x", "ingredients": []}]),
        ("saved_meals", [{"meal_id": 1, "name": "x", "servings": []}]),
    ]:
        session = _make_mock_session(json_payload=json_payload)

        class _Stub:
            pass

        stub = _Stub()
        stub.session = session

        cronometer_fetch.fetch_real_data(stub, "2025-01-01", "2025-01-31", data_type)

        # Hard assertion: no other HTTP verbs were attempted. (The mock
        # session would have raised AssertionError if they were, but
        # MagicMock attributes default to no-op when not configured —
        # double-check via call_count.)
        for verb in ("put", "patch", "delete"):
            assert getattr(session, verb).call_count == 0, (
                f"{data_type}: session.{verb} must never be called"
            )

        # All data-fetching calls (everything after auth) must be GETs.
        assert session.get.called, f"{data_type} fetcher must issue a GET"

        for call in session.get.call_args_list:
            args, kwargs = call
            url = args[0] if args else kwargs.get("url", "")
            lower = url.lower()
            for word in forbidden:
                assert word not in lower, (
                    f"{data_type}: GET URL {url!r} contains forbidden "
                    f"substring {word!r}"
                )

        # POSTs are permitted ONLY for the GWT auth/token handshake, which
        # never touches diary endpoints; assert those calls go to the
        # known auth URL.
        for call in session.post.call_args_list:
            args, kwargs = call
            url = args[0] if args else kwargs.get("url", "")
            assert url == "https://cronometer.com/cronometer/app", (
                f"{data_type}: unexpected POST to {url!r} — recipe / "
                f"saved-meal fetchers may POST only to the GWT auth endpoint"
            )
            lower = url.lower()
            for word in forbidden:
                assert word not in lower

    # foods_with_components iterates over food_ids; assert the same
    # read-only contract holds when a food_id list is supplied.
    session = _make_mock_session(json_payload={"components": [{"name": "x"}]})

    class _Stub:
        pass

    stub = _Stub()
    stub.session = session
    stub._pending_food_ids = [101, 202]

    cronometer_fetch.fetch_real_data(
        stub, "2025-01-01", "2025-01-31", "foods_with_components"
    )
    assert session.get.call_count >= len(stub._pending_food_ids)
    for call in session.get.call_args_list:
        args, kwargs = call
        url = args[0] if args else kwargs.get("url", "")
        lower = url.lower()
        for word in forbidden:
            assert word not in lower
    for verb in ("put", "patch", "delete"):
        assert getattr(session, verb).call_count == 0, (
            f"foods_with_components: session.{verb} must never be called"
        )
