import json

class CarDatabase:
    def __init__(self, json_file="cars.json"):
        self.json_file = json_file
        self.cars_data = self.load_cars_database()
        self.reference_options = self.load_reference_options()

    def load_cars_database(self):
        try:
            with open(self.json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                return []

            cars_list = []

            for item in data:
                # Обычная запись-словарь
                if isinstance(item, dict):
                    # Пропускаем служебный блок со справочниками
                    if item.get("_meta") == "REFERENCE_OPTIONS":
                        continue

                    # Берём только реальные машины, у которых есть name
                    if item.get("name"):
                        cars_list.append(item)

                # Если по ошибке встретился вложенный список — тоже разбираем его
                elif isinstance(item, list):
                    for sub_item in item:
                        if isinstance(sub_item, dict) and sub_item.get("name"):
                            cars_list.append(sub_item)

            return cars_list

        except Exception as e:
            print("Ошибка загрузки cars.json:", e)
            return []

    def load_reference_options(self):
        try:
            with open(self.json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                return {
                    "Body": [],
                    "Type": [],
                    "Special": [],
                    "Make": []
                }

            # Популярные мировые производители автомобилей
            popular_makes = [
                "Ferrari", "Lamborghini", "Porsche", "Mercedes-Benz", "BMW",
                "Audi", "Volkswagen", "Aston Martin", "Bentley", "Rolls-Royce",
                "Bugatti", "McLaren", "Pagani", "Koenigsegg", "Hennessey",
                "Lotus", "Jaguar", "Land Rover", "Maserati", "Alfa Romeo",
                "Fiat", "Lancia", "Bugatti", "Bugatti", "Citroën", "Renault",
                "Peugeot", "Toyota", "Honda", "Nissan", "Mazda", "Subaru",
                "Mitsubishi", "Hyundai", "Kia", "Tata", "Mahindra",
                "Ford", "General Motors", "Chrysler", "Tesla", "Rivian",
                "Lucid", "Polestar", "Volvo", "Saab", "Geely", "BYD",
                "GAC Aion", "NIO", "XPeng", "Li Auto", "Changan",
                "Chery", "Great Wall", "Haval", "SAIC", "FAW"
            ]

            # Собираем существующие производители из базы данных
            existing_makes = set()
            for car in self.cars_data:
                if isinstance(car, dict):
                    make_value = str(car.get("make", "")).strip()
                    if make_value:
                        existing_makes.add(make_value)

            # Объединяем: существующие + популярные, убираем дубликаты
            all_makes = sorted(set(list(existing_makes) + popular_makes), key=lambda x: x.lower())

            body_list = []
            type_list = []
            special_list = []

            for item in data:
                if isinstance(item, dict) and item.get("_meta") == "REFERENCE_OPTIONS":
                    body_list = item.get("Body", [])
                    type_list = item.get("Type", [])
                    special_list = item.get("Special", [])

                    # На всякий случай приводим к спискам
                    if not isinstance(body_list, list):
                        body_list = []
                    if not isinstance(type_list, list):
                        type_list = []
                    if not isinstance(special_list, list):
                        special_list = []

                    break

            return {
                "Body": body_list,
                "Type": type_list,
                "Special": special_list,
                "Make": all_makes
            }

        except Exception:
            return {
                "Body": [],
                "Type": [],
                "Special": [],
                "Make": []
            }

    def find_car_in_database(self, car_name):
        search_name = car_name.strip().lower()
        for car in self.cars_data:
            db_name = str(car.get("name", "")).strip().lower()
            if db_name == search_name:
                return car
        return None

    def get_car_extra_data(self, car_name):
        car_data = self.find_car_in_database(car_name)

        if car_data:
            sku = str(car_data.get("sku", "")).strip()
            brand = str(car_data.get("brand", "")).strip()

            return {
                "sku": sku,
                "brand": brand
            }

        return {
            "sku": "",
            "brand": ""
        }

    def save_new_car_to_database(self, new_car_data):
        try:
            with open(self.json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                return False

            new_name = str(new_car_data.get("name", "")).strip().lower()
            new_sku = str(new_car_data.get("sku", "")).strip().lower()

            for item in data:
                if not isinstance(item, dict):
                    continue

                existing_name = str(item.get("name", "")).strip().lower()
                existing_sku = str(item.get("sku", "")).strip().lower()

                if existing_name and existing_name == new_name:
                    return False  # Duplicate name

                if existing_sku and existing_sku == new_sku:
                    return False  # Duplicate SKU

            data.append(new_car_data)

            with open(self.json_file, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print("Ошибка записи новой машинки в cars.json: " + str(e))
            return False

    def save_edited_car_to_database(self, original_name, updated_car_data):
        try:
            with open(self.json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                return False

            original_name_lower = str(original_name).strip().lower()
            updated_name_lower = str(updated_car_data.get("name", "")).strip().lower()
            updated_sku_lower = str(updated_car_data.get("sku", "")).strip().lower()

            target_index = -1

            for index, item in enumerate(data):
                if not isinstance(item, dict):
                    continue

                item_name = str(item.get("name", "")).strip().lower()
                item_sku = str(item.get("sku", "")).strip().lower()

                # Находим редактируемую запись
                if item_name == original_name_lower and target_index == -1:
                    target_index = index
                    continue

                # Проверка дубликата имени
                if item_name and item_name == updated_name_lower:
                    return False

                # Проверка дубликата SKU
                if item_sku and item_sku == updated_sku_lower:
                    return False

            if target_index < 0:
                return False

            data[target_index] = updated_car_data

            with open(self.json_file, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print("Ошибка сохранения изменений машинки: " + str(e))
            return False

    def reload_data(self):
        self.cars_data = self.load_cars_database()
        self.reference_options = self.load_reference_options()