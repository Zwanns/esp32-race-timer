from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import json
import os

class ResultsManager:
    def __init__(self, history_table):
        self.history = history_table
        self.results_data = []
        self.last_top3_signature = ()

    def get_top3_signature(self):
        signature = []
        top_count = min(3, len(self.results_data))
        for i in range(top_count):
            row_data = self.results_data[i]
            signature.append((row_data["car"], round(row_data["time"], 3)))
        return tuple(signature)

    def find_result_index_by_car(self, car_name):
        for index, row_data in enumerate(self.results_data):
            if row_data["car"] == car_name:
                return index
        return -1

    def recalculate_gaps(self):
        if not self.results_data:
            return

        best_time = self.results_data[0]["time"]
        for row_data in self.results_data:
            if row_data["time"] == best_time:
                row_data["gap"] = "LEADER"
            else:
                gap_value = row_data["time"] - best_time
                row_data["gap"] = f"+{gap_value:.3f}"

    def apply_row_colors(self):
        gold_color = QColor("#D4AF37")
        silver_color = QColor("#C0C0C0")
        bronze_color = QColor("#CD7F32")
        default_color = QColor("#1e1e1e")
        default_text_color = QColor("#ffffff")
        top_text_color = QColor("#000000")

        for row in range(self.history.rowCount()):
            if row == 0:
                bg_color = gold_color
                text_color = top_text_color
            elif row == 1:
                bg_color = silver_color
                text_color = top_text_color
            elif row == 2:
                bg_color = bronze_color
                text_color = top_text_color
            else:
                bg_color = default_color
                text_color = default_text_color

            for col in range(self.history.columnCount()):
                item = self.history.item(row, col)
                if item is not None:
                    item.setBackground(bg_color)
                    item.setForeground(text_color)

    def refresh_results_table(self):
        old_top3_signature = self.last_top3_signature

        self.results_data.sort(key=lambda item: item["time"])
        self.recalculate_gaps()
        self.history.setRowCount(0)

        for row_index, row_data in enumerate(self.results_data):
            self.history.insertRow(row_index)

            item_place = QTableWidgetItem(str(row_index + 1))
            item_car = QTableWidgetItem(str(row_data["car"]))
            
            # Безопасное преобразование времени в float
            try:
                time_value = float(row_data["time"])
                item_time = QTableWidgetItem(f'{time_value:.3f}')
            except (ValueError, TypeError):
                item_time = QTableWidgetItem("--")
            
            item_gap = QTableWidgetItem(str(row_data["gap"]))
            item_sheets = QTableWidgetItem(str(row_data["sheets"]))

            for item in (item_place, item_car, item_time, item_gap, item_sheets):
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self.history.setItem(row_index, 0, item_place)
            self.history.setItem(row_index, 1, item_car)
            self.history.setItem(row_index, 2, item_time)
            self.history.setItem(row_index, 3, item_gap)
            self.history.setItem(row_index, 4, item_sheets)

        self.apply_row_colors()

        new_top3_signature = self.get_top3_signature()
        self.last_top3_signature = new_top3_signature

        if old_top3_signature != new_top3_signature:
            self.history.scrollToTop()

    def upsert_result(self, car_name, time_value, sheets_status, extra_data):
        existing_index = self.find_result_index_by_car(car_name)
        if existing_index >= 0:
            self.results_data[existing_index]["time"] = time_value
            self.results_data[existing_index]["sheets"] = sheets_status
            self.results_data[existing_index]["sku"] = extra_data["sku"]
            self.results_data[existing_index]["brand"] = extra_data["brand"]
        else:
            self.results_data.append({
                "car": car_name,
                "time": time_value,
                "gap": "",
                "sheets": sheets_status,
                "sku": extra_data["sku"],
                "brand": extra_data["brand"]
            })

        self.refresh_results_table()
        self.save_to_file()  # Автосохранение после добавления/обновления результата

    def clear_results(self):
        self.results_data.clear()
        self.last_top3_signature = ()
        self.history.setRowCount(0)
        self.save_to_file()  # Автосохранение после очистки

    def delete_result(self, car_name):
        existing_index = self.find_result_index_by_car(car_name)
        if existing_index >= 0:
            del self.results_data[existing_index]
            self.refresh_results_table()
            self.save_to_file()  # Автосохранение после удаления
            return True
        return False

    def update_result_names_after_edit(self, old_name, new_name):
        if old_name == new_name:
            return

        for row_data in self.results_data:
            if row_data["car"] == old_name:
                row_data["car"] = new_name

        self.refresh_results_table()

    def save_to_file(self, filename="results_data.json"):
        """Сохранить результаты в JSON файл"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.results_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения результатов: {e}")
            return False

    def load_from_file(self, filename="results_data.json"):
        """Загрузить результаты из JSON файла"""
        if not os.path.exists(filename):
            return False

        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return False
            
            # Валидация структуры данных
            for item in data:
                if not isinstance(item, dict):
                    continue
                # Убеждаемся, что все необходимые поля есть
                required_fields = ["car", "time", "gap", "sheets", "sku", "brand"]
                for field in required_fields:
                    if field not in item:
                        item[field] = ""
                # Преобразуем время в float если нужно
                try:
                    item["time"] = float(item["time"])
                except (ValueError, TypeError):
                    item["time"] = 0.0
            
            self.results_data = data
            self.refresh_results_table()
            return True
        except Exception as e:
            print(f"Ошибка загрузки результатов: {e}")
            return False