import os
import sys
import requests

def get_weather_data(api_key, location_name="臺北市"):
    """
    取得指定地點的最高溫度與最高降雨機率
    範例使用中央氣象署 F-C0032-001 (一般天氣預報-今明36小時)
    """
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
    params = {
        "Authorization": api_key,
        "locationName": location_name
    }
    
    response = requests.get(url, params=params, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"天氣 API 請求失敗，狀態碼: {response.status_code}, 回應: {response.text}")
    
    data = response.json()
    try:
        elements = data["records"]["location"][0]["weatherElement"]
        max_temp = None
        max_pop = None
        
        for elem in elements:
            # MaxT: 最高溫度
            if elem["elementName"] == "MaxT":
                temps = [int(x["parameter"]["parameterName"]) for x in elem["time"]]
                max_temp = max(temps)
            # PoP: 降雨機率
            elif elem["elementName"] == "PoP":
                pops = [int(x["parameter"]["parameterName"]) for x in elem["time"]]
                max_pop = max(pops)
                
        return max_temp, max_pop
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"解析天氣資料失敗: {e}")

def get_aqi_data(api_key, site_name="臺北"):
    """
    取得指定測站的 AQI 資料
    範例使用環境部 AQX_P_432 (空氣品質指標)
    """
    url = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
    params = {
        "api_key": api_key,
        "limit": 1000,
        "sort": "ImportDate desc",
        "format": "JSON"
    }
    
    response = requests.get(url, params=params, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"AQI API 請求失敗，狀態碼: {response.status_code}, 回應: {response.text}")
        
    data = response.json()
    try:
        for record in data.get("records", []):
            if record.get("sitename") == site_name:
                aqi_str = record.get("aqi")
                return int(aqi_str) if aqi_str else 0
        raise ValueError(f"找不到測站: {site_name}")
    except (KeyError, ValueError) as e:
        raise ValueError(f"解析 AQI 資料失敗: {e}")

def build_commute_advice(max_temp, max_pop, aqi):
    """
    根據規格產生可同時成立的多個建議
    """
    advice_list = []
    
    # 規格 3: 降雨機率達 60% 時提醒攜帶雨傘
    if max_pop >= 60:
        advice_list.append("☔ 降雨機率偏高，請攜帶雨傘！")
        
    # 規格 4: 最高溫度達 33°C 時提醒防曬與補充水分
    if max_temp >= 33:
        advice_list.append("🌡️ 氣溫偏高，請注意防曬並多補充水分！")
        
    # 規格 5: AQI 達 100 時提醒配戴口罩
    if aqi >= 100:
        advice_list.append("😷 空氣品質欠佳，外出請配戴口罩！")
        
    # 規格 6: 所有條件正常時，顯示適合外出通勤
    if not advice_list:
        advice_list.append("☀️ 今日天氣與空氣品質良好，適合外出通勤！")
        
    return advice_list

def send_telegram_message(bot_token, chat_id, message_text):
    """透過 Telegram Bot API 發送訊息"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Telegram 發送失敗，狀態碼: {response.status_code}, 回應: {response.text}")

def main():
    # 讀取環境變數 (Secrets)
    tg_token = os.environ.get("TG_BOT_TOKEN")
    tg_chat_id = os.environ.get("TG_CHAT_ID")
    cwa_key = os.environ.get("CWA_API_KEY")
    moenv_key = os.environ.get("MOENV_API_KEY")

    if not tg_token or not tg_chat_id:
        print("錯誤: 缺少 TG_BOT_TOKEN 或 TG_CHAT_ID 環境變數", file=sys.stderr)
        sys.exit(1)

    try:
        max_temp, max_pop = get_weather_data(cwa_key, location_name="臺北市")
        aqi = get_aqi_data(moenv_key, site_name="臺北")
        advices = build_commute_advice(max_temp, max_pop, aqi)

        # 組合推播訊息
        message = (
            f"🚴 *智慧通勤風險通知*\n\n"
            f"📍 地點：臺北市\n"
            f"🌡️ 最高溫度：{max_temp}°C\n"
            f"🌧️ 最高降雨機率：{max_pop}%\n"
            f"💨 空氣品質 (AQI)：{aqi}\n\n"
            f"📋 *通勤建議：*\n" + "\n".join(f"- {adv}" for adv in advices)
        )

        send_telegram_message(tg_token, tg_chat_id, message)
        print("通知已成功送出！")

    except Exception as e:
        print(f"程式執行中發生錯誤: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
