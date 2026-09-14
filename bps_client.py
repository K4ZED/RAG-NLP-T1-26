import itertools
import time

import requests

import config

BASE_URL = "https://webapi.bps.go.id/v1/api"

# The BPS "Perimeter WAF" blocks requests without a browser-like User-Agent.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class BPSError(RuntimeError):
    pass


def _get(model: str, **params) -> dict:
    params["key"] = config.BPS_API_KEY
    path = "/".join(f"{k}/{v}" for k, v in params.items())
    url = f"{BASE_URL}/list/model/{model}/lang/ind/{path}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") not in ("OK", "Error"):
        raise BPSError(f"Unexpected BPS response: {data}")
    if data.get("status") == "Error":
        raise BPSError(data.get("message", "Unknown BPS error"))
    return data


def get_subjects_page(domain: str, page: int) -> dict:
    return _get("subject", domain=domain, page=page)


def get_all_subjects(domain: str) -> list[dict]:
    subjects = []
    first = get_subjects_page(domain, 1)
    body = first["data"]
    subjects.extend(body[1])
    total_pages = body[0]["pages"]
    for page in range(2, total_pages + 1):
        time.sleep(0.2)
        body = get_subjects_page(domain, page)["data"]
        subjects.extend(body[1])
    return subjects


def get_vars_page(domain: str, subject_id: int, page: int) -> dict:
    return _get("var", domain=domain, subject=subject_id, page=page)


def get_vars(domain: str, subject_id: int, max_vars: int | None = None) -> list[dict]:
    variables: list[dict] = []
    page = 1
    while True:
        body = get_vars_page(domain, subject_id, page)["data"]
        variables.extend(body[1])
        total_pages = body[0]["pages"]
        if max_vars is not None and len(variables) >= max_vars:
            return variables[:max_vars]
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.2)
    return variables


def get_years(domain: str, var_id: int) -> list[dict]:
    years: list[dict] = []
    page = 1
    while True:
        body = _get("th", domain=domain, var=var_id, page=page)["data"]
        years.extend(body[1])
        total_pages = body[0]["pages"]
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.2)
    return years


def get_data(domain: str, var_id: int, th: str) -> dict:
    """th accepts a single th_id, or a range 'id1:id2' / list 'id1;id2'."""
    return _get("data", domain=domain, var=var_id, th=th)


def decode_records(data: dict) -> list[dict]:
    """Reconstruct (vervar, turvar, tahun, turtahun) -> value records.

    BPS encodes datacontent keys by concatenating
    f"{vervar_val}{var_id}{turvar_val}{th_id}{turtahun_val}" with no
    separators or padding. Rather than parse that ambiguous string, we
    rebuild every candidate key from the small enumerable metadata lists
    already present in the response and match it back against the
    datacontent dict. Verified against BPS live data: 180/180 keys for a
    PDRB quarterly series matched this way.
    """
    var_id = data["var"][0]["val"]
    vervar = data.get("vervar") or [{"val": "", "label": ""}]
    turvar = data.get("turvar") or [{"val": "", "label": ""}]
    tahun = data.get("tahun") or [{"val": "", "label": ""}]
    turtahun = data.get("turtahun") or [{"val": "", "label": ""}]
    datacontent = data["datacontent"]

    records = []
    for v, tv, t, tt in itertools.product(vervar, turvar, tahun, turtahun):
        key = f"{v['val']}{var_id}{tv['val']}{t['val']}{tt['val']}"
        if key in datacontent:
            records.append(
                {
                    "vervar": v["label"],
                    "turvar": tv["label"],
                    "tahun": t["label"],
                    "turtahun": tt["label"],
                    "value": datacontent[key],
                }
            )
    return records
