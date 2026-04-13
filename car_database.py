import json

BODY_TOOLTIPS = {
    "Sedan": "Классический закрытый кузов с 4 дверями и отдельным багажником.",
    "Hatchback": "Короткий кузов с задней подъемной дверью и общим салоном с багажником.",
    "Wagon": "Удлиненный кузов с увеличенным багажным отсеком, как у универсала.",
    "Pickup": "Грузовая платформа сзади и отдельная кабина спереди, как у пикапа.",
    "Coupe": "Обычно 2-дверный кузов со спортивным силуэтом.",
    "Convertible": "Открытый кузов со складной или съемной крышей.",
    "Fastback": "Крыша плавно уходит назад одной линией до хвоста машины.",
    "Shooting Brake": "Спортивное купе с удлиненной задней частью, смесь купе и универсала.",
    "Liftback": "Похож на седан, но задняя дверь поднимается вместе со стеклом.",
    "Formula 1": "Одноместный открытый кузов болида с вынесенными колесами."
}

TYPE_TOOLTIPS = {
    "City Car": "Компактная городская машина для повседневной езды.",
    "Sports Car": "Легковая спортивная машина с акцентом на управляемость и скорость.",
    "Muscle Car": "Мощное американское купе или седан с большим мотором.",
    "Supercar": "Очень быстрый и дорогой спортивный автомобиль высокого класса.",
    "Hypercar": "Экстремально быстрый и технологичный автомобиль выше уровня supercar.",
    "Open Wheel": "Гоночная машина с открытыми колесами, как у формульных серий.",
    "GT": "Гоночный или дорожный grand tourer для скорости на длинных дистанциях.",
    "Rally": "Машина, подготовленная для раллийных трасс и смешанных покрытий.",
    "Touring Car": "Силуэтная гоночная машина, близкая по форме к серийным авто.",
    "Prototype": "Специально построенный гоночный автомобиль, не основанный на серийной модели."
}

SPECIAL_TOOLTIPS = {
    "Track-only": "Версия, созданная в первую очередь для трека и максимальной скорости на трассе.",
    "Tuned": "Модифицированный автомобиль с доработками внешности, шасси или двигателя.",
    "Urban Outlaw": "Харизматичный дорожный проект в стиле restomod или кастомной городской легенды.",
    "Classic": "Классическая модель, ценимая за возраст, стиль и исторический характер.",
    "Retro": "Автомобиль с ярко выраженной стилистикой прошлых десятилетий.",
    "Gulf Livery": "Окраска в знаменитой гоночной ливрее Gulf.",
    "Falken Livery": "Окраска в фирменной гоночной ливрее Falken.",
    "Borla Livery": "Окраска в стиле гоночной ливреи Borla.",
    "Advan Racing Livery": "Окраска в фирменном гоночном стиле Advan Racing.",
    "Streat Racing": "Автомобиль в духе уличных гонок, с акцентом на скорость, стиль и дорожный характер.",
    "Police": "Полицейская версия или стилизация под служебный автомобиль."
}

class CarDatabase:
    def __init__(self, json_file="cars.json"):
        self.json_file = json_file
        self.cars_data = self.load_cars_database()
        self.reference_options = self.load_reference_options()
        self.ensure_reference_metadata_persisted()
        self.cars_data = self.load_cars_database()
        self.reference_options = self.load_reference_options()

    def _get_default_reference_options(self):
        return {
            "Body": [],
            "Type": [],
            "Special": [],
            "Make": [],
            "Brand": [],
            "BodyDescriptions": dict(BODY_TOOLTIPS),
            "TypeDescriptions": dict(TYPE_TOOLTIPS),
            "SpecialDescriptions": dict(SPECIAL_TOOLTIPS)
        }

    def _normalize_description_map(self, values):
        if not isinstance(values, dict):
            return {}

        normalized = {}
        for key, value in values.items():
            key_text = str(key).strip()
            value_text = str(value).strip()
            if key_text:
                normalized[key_text] = value_text
        return normalized

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
                return self._get_default_reference_options()

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
            existing_brands = set()
            for car in self.cars_data:
                if isinstance(car, dict):
                    make_value = str(car.get("make", "")).strip()
                    brand_value = str(car.get("brand", "")).strip()
                    if make_value:
                        existing_makes.add(make_value)
                    if brand_value:
                        existing_brands.add(brand_value)

            # Объединяем: существующие + популярные, убираем дубликаты
            all_makes = sorted(set(list(existing_makes) + popular_makes), key=lambda x: x.lower())
            all_brands = sorted(existing_brands, key=lambda x: x.lower())

            body_list = []
            type_list = []
            special_list = []
            brand_list = []
            body_descriptions = dict(BODY_TOOLTIPS)
            type_descriptions = dict(TYPE_TOOLTIPS)
            special_descriptions = dict(SPECIAL_TOOLTIPS)

            for item in data:
                if isinstance(item, dict) and item.get("_meta") == "REFERENCE_OPTIONS":
                    body_list = item.get("Body", [])
                    type_list = item.get("Type", [])
                    special_list = item.get("Special", [])
                    brand_list = item.get("Brand", [])
                    body_descriptions.update(self._normalize_description_map(item.get("BodyDescriptions", {})))
                    type_descriptions.update(self._normalize_description_map(item.get("TypeDescriptions", {})))
                    special_descriptions.update(self._normalize_description_map(item.get("SpecialDescriptions", {})))

                    # На всякий случай приводим к спискам
                    if not isinstance(body_list, list):
                        body_list = []
                    if not isinstance(type_list, list):
                        type_list = []
                    if not isinstance(special_list, list):
                        special_list = []
                    if not isinstance(brand_list, list):
                        brand_list = []

                    break

            if not brand_list:
                brand_list = all_brands

            return {
                "Body": body_list,
                "Type": type_list,
                "Special": special_list,
                "Make": all_makes,
                "Brand": brand_list,
                "BodyDescriptions": body_descriptions,
                "TypeDescriptions": type_descriptions,
                "SpecialDescriptions": special_descriptions
            }

        except Exception:
            return self._get_default_reference_options()

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

    def save_reference_options(self, updated_reference_options, rename_operations=None):
        try:
            with open(self.json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                return False

            normalized_options = {}
            for key in ("Body", "Type", "Special", "Brand"):
                raw_values = updated_reference_options.get(key, [])
                if not isinstance(raw_values, list):
                    raw_values = []

                cleaned_values = []
                seen_values = set()
                for value in raw_values:
                    text = str(value).strip()
                    lowered_text = text.lower()
                    if not text or lowered_text in seen_values:
                        continue
                    seen_values.add(lowered_text)
                    cleaned_values.append(text)

                cleaned_values.sort(key=lambda value: value.lower())
                normalized_options[key] = cleaned_values

            reference_block = {
                "_meta": "REFERENCE_OPTIONS",
                "Body": normalized_options["Body"],
                "Type": normalized_options["Type"],
                "Special": normalized_options["Special"],
                "Brand": normalized_options["Brand"],
                "BodyDescriptions": self._normalize_description_map(updated_reference_options.get("BodyDescriptions", {})),
                "TypeDescriptions": self._normalize_description_map(updated_reference_options.get("TypeDescriptions", {})),
                "SpecialDescriptions": self._normalize_description_map(updated_reference_options.get("SpecialDescriptions", {}))
            }

            reference_index = -1
            for index, item in enumerate(data):
                if isinstance(item, dict) and item.get("_meta") == "REFERENCE_OPTIONS":
                    reference_index = index
                    break

            rename_operations = rename_operations or {}
            for field_name, operations in rename_operations.items():
                if not isinstance(operations, list):
                    continue

                for operation in operations:
                    if not isinstance(operation, (list, tuple)) or len(operation) != 2:
                        continue

                    old_value = str(operation[0]).strip()
                    new_value = str(operation[1]).strip()
                    if not old_value or not new_value:
                        continue

                    for item in data:
                        if not isinstance(item, dict) or item.get("_meta") == "REFERENCE_OPTIONS":
                            continue

                        if field_name == "brand":
                            current_brand = str(item.get("brand", "")).strip()
                            if current_brand.lower() == old_value.lower():
                                item["brand"] = new_value
                            continue

                        field_values = item.get(field_name, [])
                        if not isinstance(field_values, list):
                            field_values = [field_values]

                        updated_values = []
                        changed = False
                        seen_values = set()

                        for field_value in field_values:
                            field_text = str(field_value).strip()
                            if field_text.lower() == old_value.lower():
                                field_text = new_value
                                changed = True

                            lowered_text = field_text.lower()
                            if field_text and lowered_text not in seen_values:
                                seen_values.add(lowered_text)
                                updated_values.append(field_text)

                        if changed:
                            item[field_name] = updated_values

            if reference_index >= 0:
                data[reference_index] = reference_block
            else:
                data.insert(0, reference_block)

            with open(self.json_file, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

            self.reload_data()
            return True

        except Exception as e:
            print("Ошибка сохранения справочников: " + str(e))
            return False

    def ensure_reference_metadata_persisted(self):
        try:
            with open(self.json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, list):
                return False

            reference_block = None
            for item in data:
                if isinstance(item, dict) and item.get("_meta") == "REFERENCE_OPTIONS":
                    reference_block = item
                    break

            if reference_block is None:
                return False

            changed = False

            if "Brand" not in reference_block:
                reference_block["Brand"] = list(self.reference_options.get("Brand", []))
                changed = True

            if "BodyDescriptions" not in reference_block:
                reference_block["BodyDescriptions"] = dict(self.reference_options.get("BodyDescriptions", {}))
                changed = True

            if "TypeDescriptions" not in reference_block:
                reference_block["TypeDescriptions"] = dict(self.reference_options.get("TypeDescriptions", {}))
                changed = True

            if "SpecialDescriptions" not in reference_block:
                reference_block["SpecialDescriptions"] = dict(self.reference_options.get("SpecialDescriptions", {}))
                changed = True

            if not changed:
                return False

            with open(self.json_file, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print("Ошибка миграции справочников: " + str(e))
            return False

    def reload_data(self):
        self.cars_data = self.load_cars_database()
        self.reference_options = self.load_reference_options()
