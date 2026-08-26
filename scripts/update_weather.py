from __future__ import annotations

import csv
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


JST = timezone(timedelta(hours=9))

FORECAST_URL = (
    "https://www.jma.go.jp/"
    "bosai/forecast/data/forecast/130000.json"
)

AREA_CODE = "130010"      # 東京地方
TEMP_AREA_CODE = "44132"  # 東京

OUT = Path("data/weather.csv")
ICONS = Path("icons")


CODE_TEXT = {
    "100": "晴れ",
    "101": "晴れ 時々 くもり",
    "102": "晴れ 一時 雨",
    "103": "晴れ 時々 雨",
    "110": "晴れ のち 時々 くもり",
    "111": "晴れ のち くもり",
    "112": "晴れ のち 一時 雨",
    "113": "晴れ のち 時々 雨",
    "114": "晴れ のち 雨",
    "127": "晴れ 夕方から 雨",
    "128": "晴れ 夜は 雨",
    "140": "晴れ 時々 雨・雷",

    "200": "くもり",
    "201": "くもり 時々 晴れ",
    "202": "くもり 一時 雨",
    "203": "くもり 時々 雨",
    "210": "くもり のち 時々 晴れ",
    "211": "くもり のち 晴れ",
    "212": "くもり のち 一時 雨",
    "213": "くもり のち 時々 雨",
    "214": "くもり のち 雨",
    "224": "くもり 昼頃から 雨",
    "225": "くもり 夕方から 雨",
    "226": "くもり 夜は 雨",
    "240": "くもり 時々 雨・雷",

    "300": "雨",
    "301": "雨 時々 晴れ",
    "302": "雨 時々 やむ",
    "311": "雨 のち 晴れ",
    "313": "雨 のち くもり",

    "400": "雪",
    "401": "雪 時々 晴れ",
    "402": "雪 時々 やむ",
    "411": "雪 のち 晴れ",
    "413": "雪 のち くもり",
}


def get_json(url: str):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "weather-signage/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def create_weather_icon(code: str, path: Path):
    """
    気象庁のSVG画像をダウンロードせず、
    天気コードから表示用SVGをGitHub内に生成する。
    """

    number = int(code)

    if number >= 400:
        symbol = "❄"
        color = "#73bdf2"

    elif number >= 300:
        symbol = "☂"
        color = "#00a8e8"

    elif number >= 200:
        symbol = "☁"
        color = "#aeb7c2"

    else:
        symbol = "☀"
        color = "#ffb300"

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg
  xmlns="http://www.w3.org/2000/svg"
  width="320"
  height="320"
  viewBox="0 0 320 320"
>
  <rect
    width="320"
    height="320"
    fill="white"
    fill-opacity="0"
  />

  <text
    x="160"
    y="225"
    text-anchor="middle"
    font-size="190"
    font-family="Arial, sans-serif"
    fill="{color}"
  >{symbol}</text>
</svg>
"""

    path.write_text(svg, encoding="utf-8")


def day_key(value: str) -> str:
    return value[:10]


def find_area(series, code):
    for area in series.get("areas", []):
        if area.get("area", {}).get("code") == code:
            return area

    return None


def clean_weather(text: str, code: str) -> str:
    if code in CODE_TEXT:
        return CODE_TEXT[code]

    normalized = re.sub(
        r"[　\s]+",
        " ",
        text or ""
    ).strip()

    return normalized if normalized else "予報なし"


def main():
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    ICONS.mkdir(
        parents=True,
        exist_ok=True
    )

    data = get_json(FORECAST_URL)

    short = data[0]
    weekly = data[1]

    daily = {}

    # 今日・明日の天気情報
    weather_series = short["timeSeries"][0]
    weather_area = find_area(
        weather_series,
        AREA_CODE
    )

    if not weather_area:
        raise RuntimeError(
            "東京地方の天気データが見つかりません"
        )

    for dt, code, text in zip(
        weather_series["timeDefines"],
        weather_area["weatherCodes"],
        weather_area["weathers"]
    ):
        key = day_key(dt)

        daily.setdefault(key, {}).update(
            code=code,
            weather=clean_weather(text, code)
        )

    # 週間予報から不足日を補完
    weekly_weather_series = weekly["timeSeries"][0]
    weekly_weather_area = find_area(
        weekly_weather_series,
        AREA_CODE
    )

    if weekly_weather_area:
        for dt, code, pop in zip(
            weekly_weather_series["timeDefines"],
            weekly_weather_area["weatherCodes"],
            weekly_weather_area["pops"]
        ):
            key = day_key(dt)

            daily.setdefault(key, {}).setdefault(
                "code",
                code
            )

            daily[key].setdefault(
                "weather",
                clean_weather("", code)
            )

            if pop != "":
                daily[key].setdefault(
                    "rain",
                    int(pop)
                )

    # 6時間ごとの降水確率から、その日の最大値を使用
    pop_series = short["timeSeries"][1]
    pop_area = find_area(
        pop_series,
        AREA_CODE
    )

    if pop_area:
        for dt, pop in zip(
            pop_series["timeDefines"],
            pop_area["pops"]
        ):
            if pop == "":
                continue

            key = day_key(dt)
            value = int(pop)

            previous = daily.get(
                key,
                {}
            ).get(
                "rain",
                value
            )

            daily.setdefault(key, {})["rain"] = max(
                value,
                previous
            )

    # 今日・明日の最高／最低気温
    temp_series = short["timeSeries"][2]
    temp_area = find_area(
        temp_series,
        TEMP_AREA_CODE
    )

    if temp_area:
        for dt, temp in zip(
            temp_series["timeDefines"],
            temp_area["temps"]
        ):
            if temp == "":
                continue

            key = day_key(dt)
            hour = datetime.fromisoformat(dt).hour
            value = int(temp)

            if hour == 0:
                daily.setdefault(key, {})["min"] = value

            if hour == 9:
                daily.setdefault(key, {})["max"] = value

    # 週間予報から明後日以降の最高／最低気温を補完
    weekly_temp_series = weekly["timeSeries"][1]
    weekly_temp_area = find_area(
        weekly_temp_series,
        TEMP_AREA_CODE
    )

    if weekly_temp_area:
        for dt, temp_min, temp_max in zip(
            weekly_temp_series["timeDefines"],
            weekly_temp_area["tempsMin"],
            weekly_temp_area["tempsMax"]
        ):
            key = day_key(dt)

            if temp_min != "":
                daily.setdefault(key, {}).setdefault(
                    "min",
                    int(temp_min)
                )

            if temp_max != "":
                daily.setdefault(key, {}).setdefault(
                    "max",
                    int(temp_max)
                )

    today = datetime.now(JST).date()

    labels = [
        "今日",
        "明日",
        "明後日"
    ]

    rows = []

    for offset, label in enumerate(labels):
        key = (
            today + timedelta(days=offset)
        ).isoformat()

        item = daily.get(key, {})

        code = str(
            item.get("code", "200")
        ).strip()

        # 気象庁SVGへアクセスせず、GitHub内に生成
        icon_name = f"{code}.svg"
        icon_path = ICONS / icon_name

        create_weather_icon(
            code,
            icon_path
        )

        rows.append({
            "label": label,
            "date": key,
            "weather": item.get(
                "weather",
                clean_weather("", code)
            ),
            "code": code,
            "icon": f"icons/{icon_name}",
            "temp_max": item.get("max", ""),
            "temp_min": item.get("min", ""),
            "rain": item.get("rain", "")
        })

    report_time = datetime.fromisoformat(
        short["reportDatetime"]
    ).astimezone(
        JST
    ).strftime(
        "%Y/%m/%d %H:%M"
    )

    updated_time = datetime.now(
        JST
    ).strftime(
        "%Y/%m/%d %H:%M"
    )

    fields = [
        "label",
        "date",
        "weather",
        "code",
        "icon",
        "temp_max",
        "temp_min",
        "rain",
        "report_time",
        "updated_time"
    ]

    with OUT.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fields
        )

        writer.writeheader()

        for row in rows:
            row["report_time"] = report_time
            row["updated_time"] = updated_time

            writer.writerow(row)


if __name__ == "__main__":
    main()
