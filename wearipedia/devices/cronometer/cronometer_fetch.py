import io
import re

import pandas as pd

# Set of HTTP paths this module will never call. Enforced both by code review
# and by `tests/devices/cronometer/test_cronometer.py::test_recipe_fetchers_are_read_only`.
# Any new recipe / saved-meal / components fetcher MUST go through `session.get`
# and MUST NOT touch any URL containing one of these substrings.
_FORBIDDEN_PATH_SUBSTRINGS = ("explode", "delete", "update")


def _authenticate_gwt(session):
    """Exchange the authenticated browser session for a short-lived
    Cronometer auth token.

    These calls hit the same GWT-RPC endpoints the existing
    ``dailySummary``/``servings`` flow uses. They are POSTs against the
    auth/token endpoints — they never touch user diary data, and they are
    out of scope for the read-only guard on the recipe/meal fetchers
    (which is enforced separately on the data-fetching step below).
    """
    GWTBaseURL = "https://cronometer.com/cronometer/app"
    GWTHeader = "2D6A926E3729946302DC68073CB0D550"

    body = f"7|0|5|https://cronometer.com/cronometer/|{GWTHeader}|com.cronometer.shared.rpc.CronometerService|authenticate|java.lang.Integer/3438268394|1|2|3|4|1|5|5|-480|"
    header = {
        "content-type": "text/x-gwt-rpc; charset=UTF-8",
        "x-gwt-module-base": "https://cronometer.com/cronometer/",
        "x-gwt-permutation": "7B121DC5483BF272B1BC1916DA9FA963",
    }

    res = session.post(GWTBaseURL, data=body, headers=header)

    sesnonce_cookie = session.cookies.get("sesnonce")
    sesnonce_value = sesnonce_cookie if sesnonce_cookie else None

    pattern = r"//OK\[(?P<userid>\d+),"
    match_object = re.match(pattern, res.text)
    print(pattern, res.text)

    if match_object:
        userid = match_object.group("userid")
    else:
        raise Exception(
            pattern, res.text, "Could not extract the userid, authentication failed"
        )

    if res.status_code != 200:
        raise Exception("Could not fetch the data, authentication failed")

    body = f"7|0|8|https://cronometer.com/cronometer/|{GWTHeader}|com.cronometer.shared.rpc.CronometerService|generateAuthorizationToken|java.lang.String/2004016611|I|com.cronometer.shared.user.AuthScope/2065601159|{sesnonce_value}|1|2|3|4|4|5|6|6|7|8|{userid}|3600|7|2|"
    auth_token = session.post(GWTBaseURL, headers=header, data=body)

    if auth_token.status_code != 200:
        raise Exception("Could not fetch the data, authentication failed")

    return auth_token.text.split('"')[1]


def _assert_safe_path(url):
    lower = url.lower()
    for forbidden in _FORBIDDEN_PATH_SUBSTRINGS:
        if forbidden in lower:
            raise Exception(
                f"Refusing to call URL containing forbidden substring "
                f"'{forbidden}': {url}. Recipe / saved-meal fetchers are "
                f"read-only by contract."
            )


def _fetch_recipes(session, auth_token, start_date, end_date):
    """Read the user's Custom Recipes via a single GET.

    The actual Cronometer endpoint that powers the recipe-list panel in
    the web UI is not yet finalized in this stub; it should be discovered
    by inspecting the requests the web UI makes when rendering the
    Recipes section BEFORE the user clicks Explode. Whatever endpoint
    that is, it must be invoked with ``session.get`` only — this function
    asserts that contract.

    The recipe list is account-scoped, not date-scoped, so ``start_date``
    / ``end_date`` are accepted for signature parity with the other
    fetchers but not forwarded to the request.

    Returns a list of
    ``{recipe_id, name, servings_per_recipe, ingredients: [...]}``.
    """
    del start_date, end_date  # account-scoped, not date-scoped
    url = "https://cronometer.com/recipes"
    _assert_safe_path(url)
    params = {"nonce": auth_token}
    res = session.get(url, params=params)
    if res.status_code != 200:
        raise Exception(
            f"Failed to fetch recipes from {url}: HTTP {res.status_code}. "
            f"This endpoint is a stub — see _fetch_recipes docstring."
        )
    try:
        payload = res.json()
    except ValueError:
        raise Exception(
            f"Recipe endpoint at {url} did not return JSON. Stub URL "
            f"likely needs updating; see _fetch_recipes docstring."
        )
    return payload if isinstance(payload, list) else payload.get("recipes", [])


def _fetch_saved_meals(session, auth_token, start_date, end_date):
    """Read the user's Saved Meals via a single GET. Same contract /
    same stub caveat as :func:`_fetch_recipes`."""
    del start_date, end_date  # account-scoped, not date-scoped
    url = "https://cronometer.com/saved_meals"
    _assert_safe_path(url)
    params = {"nonce": auth_token}
    res = session.get(url, params=params)
    if res.status_code != 200:
        raise Exception(
            f"Failed to fetch saved meals from {url}: HTTP {res.status_code}. "
            f"This endpoint is a stub — see _fetch_saved_meals docstring."
        )
    try:
        payload = res.json()
    except ValueError:
        raise Exception(
            f"Saved meals endpoint at {url} did not return JSON. Stub URL "
            f"likely needs updating; see _fetch_saved_meals docstring."
        )
    return payload if isinstance(payload, list) else payload.get("saved_meals", [])


def _fetch_foods_with_components(session, auth_token, food_ids):
    """Per-food lookup for any ``food_id`` whose Cronometer record
    exposes a ``components``/``ingredients`` list (e.g. branded packaged
    foods Cronometer has pre-decomposed). Read-only — issues only GETs,
    one per food_id.

    ``food_ids`` is passed in by the caller (typically the ibs-cronometer
    pipeline, which extracts them from the previously-fetched servings
    DataFrame) via the ``params={"food_ids": [...]}`` argument on
    ``device.get_data("foods_with_components", params=...)``.

    Returns ``{food_id: [ingredient_dict, ...]}`` (only foods that
    actually have components are included). Individual food lookups that
    404 are skipped rather than failing the whole batch — most foods in
    Cronometer's database don't have components and that's expected."""
    out = {}
    food_ids = food_ids or []
    for fid in food_ids:
        url = "https://cronometer.com/food"
        _assert_safe_path(url)
        params = {"nonce": auth_token, "food_id": int(fid)}
        res = session.get(url, params=params)
        if res.status_code != 200:
            continue
        try:
            payload = res.json()
        except ValueError:
            continue
        components = payload.get("components") or payload.get("ingredients")
        if components:
            out[int(fid)] = components
    return out


def fetch_real_data(self, start_date, end_date, data_type):
    """Main function for fetching real data from the Cronometer API.

    :param start_date: the start date represented as a string in the format "YYYY-MM-DD"
    :type start_date: str
    :param end_date: the end date represented as a string in the format "YYYY-MM-DD"
    :type end_date: str
    :param data_type: the type of data to fetch, one of "dailySummary", "servings",
        "exercises", "biometrics", "recipes", "saved_meals", "foods_with_components"
    :type data_type: str
    :return: the data fetched from the API according to the inputs
    :rtype: List or Dict
    """

    # This function is called when we want to fetch real data from the
    # device. It is called by the _get_real function in the base class.

    # We need to authenticate first, if we haven't already.
    if self.session is None:
        raise Exception("Not authenticated")

    auth_token = _authenticate_gwt(self.session)

    if data_type == "recipes":
        return _fetch_recipes(self.session, auth_token, start_date, end_date)
    if data_type == "saved_meals":
        return _fetch_saved_meals(self.session, auth_token, start_date, end_date)
    if data_type == "foods_with_components":
        food_ids = getattr(self, "_pending_food_ids", []) or []
        return _fetch_foods_with_components(self.session, auth_token, food_ids)

    # creating the parameters for the get request
    params = {
        "nonce": auth_token,
        "generate": data_type,
        "start": start_date,
        "end": end_date,
    }

    # creating the url for the get request
    data = self.session.get("https://cronometer.com/export", params=params)

    # parsing the data
    content = data.content

    # creating a dataframe from the data
    try:
        content_utf = content.decode("utf-8")

        # Double-quote the biometrics with [min,max] notation that break the CSV string parsing
        # hard-coded to these particular user-defined biometrics
        content_utf = content_utf.replace("Badness [0,3]", '"Badness [0,3]"')
        content_utf = content_utf.replace("Discomfort [0,3]", '"Discomfort [0,3]"')
        content_utf = content_utf.replace("Badness [0,4]", '"Badness [0,4]"')

        # print("Content UTF:")
        # print(content_utf)
        # print("\n" + "=" * 80 + "\n")

        df = pd.read_csv(io.StringIO(content_utf))
    except Exception as e:
        print(f"Error parsing data: {e}")
        raise

    # returning the dataframe
    return list(df.to_dict("index").values())
