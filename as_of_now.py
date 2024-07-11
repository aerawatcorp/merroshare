import requests
from copy import deepcopy

from flask import Flask, render_template
from datetime import datetime

from credentials import demat, dp_id, client_id, username, password

root = "https://webbackend.cdsc.com.np/api"

wacc_url = "/myPurchase/waccReport/"
portfolio_url = "/meroShareView/myPortfolio/"
login_url = "/meroShare/auth/"

_headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,ne-NP;q=0.8,ne;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Origin": "https://meroshare.cdsc.com.np",
    "Pragma": "no-cache",
    "Referer": "https://meroshare.cdsc.com.np/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
}

print_keys = [
    "scrip",
    "scrip_desc",
    "qty",
    "cost_per_unit",
    "cost",
    "ltp",
    "ltp_closing",
    "eps_closing",
    "eps_ltp",
    "gain_closing",
    "gain_ltp",
    "gain_closing_percent",
    "gain_ltp_percent",
    "_",
    "trend_gain",
]

numeric_keys = [x for x in print_keys if x not in ["scrip", "scrip_desc", "_"]]

_token_file = "auth_token.txt"
try:
    _auth_token = open(_token_file, "r").read() if _token_file else None
except Exception as exc:
    open(_token_file, "w+").write("")
    _auth_token = None

from requests import session

this_session = session()


def login():
    global _auth_token
    if _auth_token:
        return _auth_token
    url = root + login_url
    login_data = {"clientId": client_id, "username": username, "password": password}
    response = this_session.post(url, headers=_headers, json=login_data)
    resp_headers = response.headers
    if response.status_code != 200:
        raise Exception("Login Failed")
    _auth_token = resp_headers.get("Authorization")

    open(_token_file, "w+").write(_auth_token)
    return _auth_token


def logged_in_headers():
    auth_token = login()
    headers = deepcopy(_headers)
    headers.update({"Authorization": auth_token})
    return headers


def get_wacc():
    url = root + wacc_url
    response = this_session.post(
        url, headers=logged_in_headers(), json={"demat": demat}
    )
    return response.json()


def get_portfolio():
    url = root + portfolio_url
    response = this_session.post(
        url,
        headers=logged_in_headers(),
        json={
            "sortBy": "script",
            "demat": [demat],
            "clientCode": dp_id,
            "page": 1,
            "size": 200,
            "sortAsc": True,
        },
    )
    return response.json()


def compare():
    wacc = get_wacc()
    portfolio = get_portfolio()

    wacc_key_maps = {
        "scrip": "scrip",
        "totalQuantity": "qty",
        "averageBuyRate": "cost_per_unit",
        "totalCost": "cost",
        "lastModifiedDate": "last_modified",
        "demat": "demat",
    }

    wacc_summary = {}

    for w in wacc.get("waccReportResponse", []):
        for key, value in wacc_key_maps.items():
            w[value] = w.pop(key)
        _scrip = w["scrip"]
        _demat = w["demat"]
        wacc_summary[f"{_demat}_{_scrip}"] = deepcopy(w)

    portfolio_key_maps = {
        "currentBalance": "qty",
        "lastTransactionPrice": "ltp",
        "previousClosingPrice": "ltp_closing",
        "script": "scrip",
        "scriptDesc": "scrip_desc",
    }

    for pp in portfolio.get("meroShareMyPortfolio", []):
        for key, value in portfolio_key_maps.items():
            pp[value] = pp.pop(key)
        _scrip = pp["scrip"]

        portfolio_key = f"{demat}_{_scrip}"
        portfolio_cost_per_unit = wacc_summary[portfolio_key]["cost_per_unit"]
        portfolio_qty = wacc_summary[portfolio_key]["qty"]

        eps_closing = float(pp["ltp_closing"]) - float(portfolio_cost_per_unit)
        eps_ltp = float(pp["ltp"]) - float(portfolio_cost_per_unit)

        gain_closing = eps_closing * float(portfolio_qty)
        gain_ltp = eps_ltp * float(portfolio_qty)

        wacc_summary[portfolio_key].update(
            {
                "ltp": pp["ltp"],
                "ltp_closing": pp["ltp_closing"],
                "scrip_desc": pp["scrip_desc"],
                "eps_closing": eps_closing,
                "eps_ltp": eps_ltp,
                "gain_closing": gain_closing,
                "gain_ltp": gain_ltp,
                "gain_closing_percent": ((eps_closing / portfolio_cost_per_unit) * 100),
                "gain_ltp_percent": ((eps_ltp / portfolio_cost_per_unit) * 100),
                "trend_gain": eps_ltp - eps_closing,
            }
        )

    for key, value in wacc_summary.items():
        for k in numeric_keys:
            if k == "qty":
                continue
            try:
                wacc_summary[key][k] = float(wacc_summary[key][k]).__round__(2)
            except KeyError:
                pass

    return wacc_summary


app = Flask(__name__)


@app.route("/")
def compare_html():
    comparision = compare()
    nowtime = datetime.now()

    if not comparision:
        # reset login tokens
        open(_token_file, "w").write("")
        _auth_token = None

    return render_template(
        "/portfolio.html", portfolio=comparision, keys=print_keys, now=nowtime
    )


@app.route("/json")
def compare_json():
    comparision = compare()
    nowtime = datetime.now()

    if not comparision:
        # reset login tokens
        open(_token_file, "w").write("")
        _auth_token = None

    return comparision


if __name__ == "__main__":
    app.run(port=5000, debug=True)
