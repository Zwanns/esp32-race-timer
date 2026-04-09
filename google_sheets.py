import urllib.request
import urllib.error
import json

class GoogleSheetsManager:
    def __init__(self, webapp_url="https://script.google.com/macros/s/AKfycbwC2D8vVUZTi9cpQAloBfx8_PYufiq4v_AX3dzaI_icqb7qjYCWrC8tn4_tXbcK_d5i/exec"):
        self.webapp_url = webapp_url

    def send_time_to_sheets(self, time_value, car_name=""):
        try:
            payload_dict = {
                "time_s": round(time_value, 3),
                "car": car_name
            }

            payload = json.dumps(payload_dict).encode("utf-8")

            request = urllib.request.Request(
                self.webapp_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                response_text = response.read().decode("utf-8")

            return '"ok":true' in response_text or '"ok": true' in response_text

        except urllib.error.HTTPError as e:
            try:
                error_text = e.read().decode("utf-8")
                print(f"HTTP ошибка Google Sheets: {e.code} | {error_text}")
            except Exception:
                print(f"HTTP ошибка Google Sheets: {e.code}")
            return False

        except Exception as e:
            print("Ошибка отправки в Google Sheets: " + str(e))
            return False

    def send_all_results_to_sheets(self, results_data):
        try:
            payload_dict = {
                "results": []
            }

            for row in results_data:
                payload_dict["results"].append({
                    "car": row.get("car", ""),
                    "time_s": round(float(row.get("time", 0)), 3),
                    "gap": row.get("gap", ""),
                    "brand": row.get("brand", ""),
                    "sku": row.get("sku", "")
                })

            payload = json.dumps(payload_dict).encode("utf-8")

            request = urllib.request.Request(
                self.webapp_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=15) as response:
                response_text = response.read().decode("utf-8")

            return '"ok":true' in response_text or '"ok": true' in response_text

        except urllib.error.HTTPError as e:
            try:
                error_text = e.read().decode("utf-8")
                print(f"HTTP ошибка массовой отправки в Google Sheets: {e.code} | {error_text}")
            except Exception:
                print(f"HTTP ошибка массовой отправки в Google Sheets: {e.code}")
            return False

        except Exception as e:
            print("Ошибка массовой отправки в Google Sheets: " + str(e))
            return False