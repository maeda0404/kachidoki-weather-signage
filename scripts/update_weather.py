from __future__ import annotations

import csv
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/130000.json"
AREA_CODE = "130010"
TEMP_AREA_CODE = "44132"
OUT = Path("data/weather.csv")
ICONS = Path("icons")

CODE_TEXT = {
    "100":"晴れ", "101":"晴れ 時々 くもり", "102":"晴れ 一時 雨", "103":"晴れ 時々 雨",
    "110":"晴れ のち 時々 くもり", "111":"晴れ のち くもり", "112":"晴れ のち 一時 雨",
    "113":"晴れ のち 時々 雨", "114":"晴れ のち 雨", "127":"晴れ 夕方から 雨",
    "128":"晴れ 夜は 雨", "140":"晴れ 時々 雨・雷", "200":"くもり",
    "201":"くもり 時々 晴れ", "202":"くもり 一時 雨", "203":"くもり 時々 雨",
    "210":"くもり のち 時々 晴れ", "211":"くもり のち 晴れ", "212":"くもり のち 一時 雨",
    "213":"くもり のち 時々 雨", "214":"くもり のち 雨", "224":"くもり 昼頃から 雨",
    "225":"くもり 夕方から 雨", "226":"くもり 夜は 雨", "240":"くもり 時々 雨・雷",
    "300":"雨", "301":"雨 時々 晴れ", "302":"雨 時々 やむ", "311":"雨 のち 晴れ",
    "313":"雨 のち くもり", "400":"雪", "401":"雪 時々 晴れ", "402":"雪 時々 やむ",
    "411":"雪 のち 晴れ", "413":"雪 のち くもり"
}

def get_json(url: str):
    print(f"JMA JSON URL: {url}", flush=True)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/json,text/plain,*/*"
        ),
        "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
        "Referer": "https://www.jma.go.jp/bosai/forecast/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:
            print(
                f"JMA response status: {response.status}",
                flush=True
            )

            return json.load(response)

    except urllib.error.HTTPError as error:
        print(
            f"JMA HTTP error: "
            f"{error.code} {error.reason}",
            flush=True
        )

        print(
            f"JMA error URL: {error.url}",
            flush=True
        )

        raise

def create_weather_icon(code: str, path: Path):
    number = int(code)
    if number >= 400:
        symbol, color = "❄", "#73bdf2"
    elif number >= 300:
        symbol, color = "☂", "#00a8e8"
    elif number >= 200:
        symbol, color = "☁", "#aeb7c2"
    else:
        symbol, color = "☀", "#ffb300"
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">
  <rect width="320" height="320" fill="white" fill-opacity="0"/>
  <text x="160" y="225" text-anchor="middle" font-size="190" font-family="Arial, sans-serif" fill="{color}">{symbol}</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")

def day_key(value: str) -> str:
    return value[:10]

def find_area(series, code):
    return next((a for a in series.get("areas", []) if a.get("area", {}).get("code") == code), None)

def clean_weather(text: str, code: str) -> str:
    if code in CODE_TEXT:
        return CODE_TEXT[code]
    normalized = re.sub(r"[　\s]+", " ", text or "").strip()
    return normalized or "予報なし"

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)
    short, weekly = get_json(FORECAST_URL)[:2]
    daily = {}

    series = short["timeSeries"][0]
    area = find_area(series, AREA_CODE)
    if not area:
        raise RuntimeError("東京地方の天気データが見つかりません")
    for dt, code, text in zip(series["timeDefines"], area["weatherCodes"], area["weathers"]):
        daily.setdefault(day_key(dt), {}).update(code=code, weather=clean_weather(text, code))

    series = weekly["timeSeries"][0]
    area = find_area(series, AREA_CODE)
    if area:
        for dt, code, pop in zip(series["timeDefines"], area["weatherCodes"], area["pops"]):
            key = day_key(dt)
            daily.setdefault(key, {}).setdefault("code", code)
            daily[key].setdefault("weather", clean_weather("", code))
            if pop != "":
                daily[key].setdefault("rain", int(pop))

    series = short["timeSeries"][1]
    area = find_area(series, AREA_CODE)
    if area:
        for dt, pop in zip(series["timeDefines"], area["pops"]):
            if pop == "":
                continue
            key, value = day_key(dt), int(pop)
            daily.setdefault(key, {})["rain"] = max(value, daily.get(key, {}).get("rain", value))

    series = short["timeSeries"][2]
    area = find_area(series, TEMP_AREA_CODE)
    if area:
        for dt, temp in zip(series["timeDefines"], area["temps"]):
            if temp == "":
                continue
            key, hour, value = day_key(dt), datetime.fromisoformat(dt).hour, int(temp)
            if hour == 0:
                daily.setdefault(key, {})["min"] = value
            if hour == 9:
                daily.setdefault(key, {})["max"] = value

    series = weekly["timeSeries"][1]
    area = find_area(series, TEMP_AREA_CODE)
    if area:
        for dt, tmin, tmax in zip(series["timeDefines"], area["tempsMin"], area["tempsMax"]):
            key = day_key(dt)
            if tmin != "":
                daily.setdefault(key, {}).setdefault("min", int(tmin))
            if tmax != "":
                daily.setdefault(key, {}).setdefault("max", int(tmax))

    rows = []
    today = datetime.now(JST).date()
    for offset, label in enumerate(["今日", "明日", "明後日"]):
        key = (today + timedelta(days=offset)).isoformat()
        item = daily.get(key, {})
        code = str(item.get("code", "200")).strip()
        icon_name = f"{code}.svg"
        create_weather_icon(code, ICONS / icon_name)
        rows.append({"label":label, "date":key, "weather":item.get("weather", clean_weather("", code)), "code":code, "icon":f"icons/{icon_name}", "temp_max":item.get("max", ""), "temp_min":item.get("min", ""), "rain":item.get("rain", "")})

    report = datetime.fromisoformat(short["reportDatetime"]).astimezone(JST).strftime("%Y/%m/%d %H:%M")
    updated = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
    fields = ["label","date","weather","code","icon","temp_max","temp_min","rain","report_time","updated_time"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            row["report_time"], row["updated_time"] = report, updated
            writer.writerow(row)

if __name__ == "__main__":
    main()
