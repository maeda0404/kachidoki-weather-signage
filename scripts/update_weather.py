from __future__ import annotations
import csv
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/130000.json"
AREA_CODE = "130010"      # 東京地方
TEMP_AREA_CODE = "44132"  # 東京
OUT = Path("data/weather.csv")
ICONS = Path("icons")

CODE_TEXT = {
    "100":"晴れ","101":"晴れ 時々 くもり","102":"晴れ 一時 雨","103":"晴れ 時々 雨",
    "110":"晴れ のち 時々 くもり","111":"晴れ のち くもり","112":"晴れ のち 一時 雨",
    "113":"晴れ のち 時々 雨","114":"晴れ のち 雨","127":"晴れ 夕方から 雨",
    "128":"晴れ 夜は 雨","140":"晴れ 時々 雨・雷",
    "200":"くもり","201":"くもり 時々 晴れ","202":"くもり 一時 雨","203":"くもり 時々 雨",
    "210":"くもり のち 時々 晴れ","211":"くもり のち 晴れ","212":"くもり のち 一時 雨",
    "213":"くもり のち 時々 雨","214":"くもり のち 雨","224":"くもり 昼頃から 雨",
    "225":"くもり 夕方から 雨","226":"くもり 夜は 雨","240":"くもり 時々 雨・雷",
    "300":"雨","301":"雨 時々 晴れ","302":"雨 時々 やむ","311":"雨 のち 晴れ","313":"雨 のち くもり",
    "400":"雪","401":"雪 時々 晴れ","402":"雪 時々 やむ","411":"雪 のち 晴れ","413":"雪 のち くもり"
}

def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent":"weather-signage/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def download(url: str, path: Path):
    req = urllib.request.Request(url, headers={"User-Agent":"weather-signage/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        path.write_bytes(r.read())

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
    text = re.sub(r"[　\s]+", " ", text or "").strip()
    return text if text else "予報なし"

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)
    data = get_json(FORECAST_URL)
    short, weekly = data[0], data[1]
    daily = {}

    # 今日・明日・明後日の天気
    weather_series = short["timeSeries"][0]
    area = find_area(weather_series, AREA_CODE)
    if not area:
        raise RuntimeError("東京地方の天気データが見つかりません")
    for dt, code, text in zip(weather_series["timeDefines"], area["weatherCodes"], area["weathers"]):
        daily.setdefault(day_key(dt), {}).update(code=code, weather=clean_weather(text, code))

    # 週間側で不足日を補完
    wseries = weekly["timeSeries"][0]
    warea = find_area(wseries, AREA_CODE)
    if warea:
        for dt, code, pop in zip(wseries["timeDefines"], warea["weatherCodes"], warea["pops"]):
            daily.setdefault(day_key(dt), {}).setdefault("code", code)
            daily[day_key(dt)].setdefault("weather", clean_weather("", code))
            if pop != "": daily[day_key(dt)].setdefault("rain", int(pop))

    # 6時間ごとの降水確率は、その日の最大値
    pop_series = short["timeSeries"][1]
    pop_area = find_area(pop_series, AREA_CODE)
    if pop_area:
        for dt, pop in zip(pop_series["timeDefines"], pop_area["pops"]):
            key = day_key(dt); value = int(pop)
            daily.setdefault(key, {})["rain"] = max(value, daily.get(key, {}).get("rain", value))

    # 日別最高・最低気温
    temp_series = short["timeSeries"][2]
    temp_area = find_area(temp_series, TEMP_AREA_CODE)
    if temp_area:
        for dt, temp in zip(temp_series["timeDefines"], temp_area["temps"]):
            key = day_key(dt); hour = datetime.fromisoformat(dt).hour; value = int(temp)
            if hour == 0: daily.setdefault(key, {})["min"] = value
            if hour == 9: daily.setdefault(key, {})["max"] = value

    # 週間側で明後日以降の最高・最低を補完
    wt_series = weekly["timeSeries"][1]
    wt_area = find_area(wt_series, TEMP_AREA_CODE)
    if wt_area:
        for dt, tmin, tmax in zip(wt_series["timeDefines"], wt_area["tempsMin"], wt_area["tempsMax"]):
            key = day_key(dt)
            if tmin != "": daily.setdefault(key, {}).setdefault("min", int(tmin))
            if tmax != "": daily.setdefault(key, {}).setdefault("max", int(tmax))

    today = datetime.now(JST).date()
    labels = ["今日", "明日", "明後日"]
    rows = []
    for offset, label in enumerate(labels):
        key = (today + timedelta(days=offset)).isoformat()
        item = daily.get(key, {})
      code = str(item.get("code", "200")).strip()

# 一部の天気コードは同じSVG画像を共用している
ICON_FILE_MAP = {
    "103": "102",
    "105": "104",
    "107": "102",
    "108": "102",
    "111": "110",
    "113": "112",
    "114": "112",
    "116": "115",
    "117": "115",
    "118": "112",
    "119": "112",
    "120": "102",
    "121": "102",
    "122": "112",
    "123": "100",
    "124": "100",
    "125": "112",
    "126": "112",
    "127": "112",
    "128": "112",
    "131": "100",
    "132": "101",
    "140": "102",
    "160": "104",
    "170": "104",
    "181": "115",

    "203": "202",
    "205": "204",
    "207": "202",
    "208": "202",
    "211": "210",
    "213": "212",
    "214": "212",
    "216": "215",
    "217": "215",
    "218": "212",
    "219": "212",
    "220": "202",
    "221": "202",
    "222": "212",
    "223": "201",
    "224": "212",
    "225": "212",
    "226": "212",
    "228": "215",
    "229": "215",
    "230": "215",
    "231": "200",
    "240": "202",
    "250": "204",
    "260": "204",
    "270": "204",
    "281": "215",

    "304": "300",
    "306": "300",
    "309": "303",
    "316": "311",
    "317": "313",
    "320": "311",
    "321": "313",
    "322": "303",
    "323": "311",
    "324": "311",
    "325": "311",
    "326": "303",
    "327": "303",
    "328": "300",
    "329": "300",
    "340": "400",
    "350": "300",
    "361": "411",
    "371": "413",

    "405": "400",
    "409": "403",
    "414": "403",
    "420": "411",
    "421": "413",
    "422": "403",
    "423": "403",
    "425": "400",
    "426": "400",
    "427": "400",
    "450": "400"
}

svg_code = ICON_FILE_MAP.get(code, code)
icon_name = f"{svg_code}.svg"
icon_path = ICONS / icon_name

try:
    download(
        f"https://www.jma.go.jp/bosai/forecast/img/{svg_code}.svg",
        icon_path
    )
except Exception as error:
    # 直接対応するSVGが存在しない場合は、
    # 晴れ・くもり・雨・雪の基本アイコンへ切り替える
    number = int(code)

    if number >= 400:
        fallback_code = "400"
    elif number >= 300:
        fallback_code = "300"
    elif number >= 200:
        fallback_code = "200"
    else:
        fallback_code = "100"

    icon_name = f"{fallback_code}.svg"
    icon_path = ICONS / icon_name

    if not icon_path.exists():
        download(
            f"https://www.jma.go.jp/bosai/forecast/img/{fallback_code}.svg",
            icon_path
        )
        rows.append({
            "label": label, "date": key, "weather": item.get("weather", clean_weather("", code)),
            "code": code, "icon": f"icons/{icon_name}",
            "temp_max": item.get("max", ""), "temp_min": item.get("min", ""),
            "rain": item.get("rain", "")
        })

    report = datetime.fromisoformat(short["reportDatetime"]).astimezone(JST).strftime("%Y/%m/%d %H:%M")
    updated = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
    fields = ["label","date","weather","code","icon","temp_max","temp_min","rain","report_time","updated_time"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            row["report_time"] = report; row["updated_time"] = updated
            writer.writerow(row)

if __name__ == "__main__":
    main()
