import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt

class AddCarDialog(QDialog):
    def __init__(self, reference_options, existing_cars=None, car_data=None, duplicate_source_data=None, parent=None):
        super().__init__(parent)

        self.reference_options = reference_options
        self.existing_cars = existing_cars or []
        self.result_car_data = None
        self.is_edit_mode = car_data is not None
        self.is_duplicate_mode = duplicate_source_data is not None
        self.original_sku = str(car_data.get("sku", "")).strip().lower() if car_data else ""
        # Для нового авто Name собирается автоматически.
        # Для редактирования авто-сборка отключена.
        self.auto_name_enabled = not self.is_edit_mode

        if self.is_edit_mode:
            self.setWindowTitle("Редактировать авто")
        elif self.is_duplicate_mode:
            self.setWindowTitle("Дублировать авто")
        else:
            self.setWindowTitle("Добавить авто в базу")

        self.setMinimumWidth(760)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)

        # ===== ПОЛЯ ВВОДА =====
        fields_grid = QGridLayout()
        fields_grid.setHorizontalSpacing(12)
        fields_grid.setVerticalSpacing(8)

        self.name_input = QLineEdit()
        self.make_combo = QComboBox()
        self.make_combo.setEditable(True)  # Можно вводить вручную
        make_options = reference_options.get("Make", [])
        self.make_combo.addItems(make_options)
        self.make_combo.currentTextChanged.connect(self.update_auto_name)
        
        self.model_input = QLineEdit()
        self.color_input = QLineEdit()
        self.weight_input = QLineEdit()
        # Автосборка Name для нового авто
        self.model_input.textChanged.connect(self.update_auto_name)
        self.color_input.textChanged.connect(self.update_auto_name)
        self.weight_input.setPlaceholderText("00.0")
        self.weight_input.setInputMask("99.9")
        self.sku_input = QLineEdit()
        self.sku_input.textChanged.connect(self.on_sku_changed)

        self.brand_combo = QComboBox()
        self.brand_combo.addItems(["Hot Wheels", "Matchbox"])

        fields_grid.addWidget(QLabel("Name"), 0, 0)
        fields_grid.addWidget(self.name_input, 0, 1)

        fields_grid.addWidget(QLabel("Make"), 1, 0)
        fields_grid.addWidget(self.make_combo, 1, 1)

        fields_grid.addWidget(QLabel("Model"), 2, 0)
        fields_grid.addWidget(self.model_input, 2, 1)

        fields_grid.addWidget(QLabel("Color"), 3, 0)
        fields_grid.addWidget(self.color_input, 3, 1)

        fields_grid.addWidget(QLabel("Weight_g"), 4, 0)
        fields_grid.addWidget(self.weight_input, 4, 1)

        fields_grid.addWidget(QLabel("Brand"), 5, 0)
        fields_grid.addWidget(self.brand_combo, 5, 1)

        fields_grid.addWidget(QLabel("SKU"), 6, 0)
        fields_grid.addWidget(self.sku_input, 6, 1)

        self.sku_status_label = QLabel("")
        self.sku_status_label.setStyleSheet("font-size: 11px;")
        self.sku_status_label.setVisible(False)
        fields_grid.addWidget(self.sku_status_label, 7, 1)

        main_layout.addLayout(fields_grid)

        # ===== ЧЕКБОКСЫ BODY / TYPE / SPECIAL =====
        checkbox_groups_layout = QHBoxLayout()
        checkbox_groups_layout.setSpacing(12)

        self.body_checkboxes = []
        self.type_checkboxes = []
        self.special_checkboxes = []

        # ----- Body -----
        body_box = QGroupBox("Body")
        body_layout = QVBoxLayout()
        for item in self.reference_options.get("Body", []):
            checkbox = QCheckBox(item)
            self.body_checkboxes.append(checkbox)
            body_layout.addWidget(checkbox)
        body_layout.addStretch()
        body_box.setLayout(body_layout)

        # ----- Type -----
        type_box = QGroupBox("Type")
        type_layout = QVBoxLayout()
        for item in self.reference_options.get("Type", []):
            checkbox = QCheckBox(item)
            self.type_checkboxes.append(checkbox)
            type_layout.addWidget(checkbox)
        type_layout.addStretch()
        type_box.setLayout(type_layout)

        # ----- Special -----
        special_box = QGroupBox("Special")
        special_layout = QVBoxLayout()
        for item in self.reference_options.get("Special", []):
            checkbox = QCheckBox(item)
            self.special_checkboxes.append(checkbox)
            special_layout.addWidget(checkbox)
        special_layout.addStretch()
        special_box.setLayout(special_layout)

        checkbox_groups_layout.addWidget(body_box)
        checkbox_groups_layout.addWidget(type_box)
        checkbox_groups_layout.addWidget(special_box)

        main_layout.addLayout(checkbox_groups_layout)

        # ===== КНОПКИ =====
        buttons_layout = QHBoxLayout()

        if self.is_edit_mode:
            self.add_btn = QPushButton("Сохранить изменения")
        else:
            self.add_btn = QPushButton("Добавить в базу")

        self.cancel_btn = QPushButton("Отмена")

        self.add_btn.clicked.connect(self.validate_and_accept)
        self.cancel_btn.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.add_btn)
        buttons_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(buttons_layout)

        self.setLayout(main_layout)

        # Если это режим редактирования — заполняем форму текущими данными
        if car_data:
            self.fill_form_from_car_data(car_data)
        elif duplicate_source_data:
            self.fill_form_from_car_data(
                duplicate_source_data,
                keep_auto_name=True,
                clear_sku=True
            )

        self.on_sku_changed(self.sku_input.text())

    # ===== ДОБАВЛЕНИЕ/РЕДАКТИРОВАНИЕ: ЗАПОЛНИТЬ ФОРМУ =====
    def fill_form_from_car_data(self, car_data, keep_auto_name=False, clear_sku=False):
        # При редактировании не даём авто-сборке перетирать существующее имя
        self.auto_name_enabled = keep_auto_name
        if not keep_auto_name:
            self.name_input.setText(str(car_data.get("name", "")))
        
        make_value = str(car_data.get("make", "")).strip()
        make_index = self.make_combo.findText(make_value)
        if make_index >= 0:
            self.make_combo.setCurrentIndex(make_index)
        else:
            self.make_combo.setCurrentText(make_value)
        
        self.model_input.setText(str(car_data.get("model", "")))
        self.color_input.setText(str(car_data.get("color", "")))
        self.weight_input.setText(str(car_data.get("weight_g", "")))
        self.sku_input.setText("" if clear_sku else str(car_data.get("sku", "")))

        brand_value = str(car_data.get("brand", "")).strip()
        brand_index = self.brand_combo.findText(brand_value)
        if brand_index >= 0:
            self.brand_combo.setCurrentIndex(brand_index)

        body_values = car_data.get("Body", [])
        type_values = car_data.get("Type", [])
        special_values = car_data.get("Special", [])

        if not isinstance(body_values, list):
            body_values = [body_values]
        if not isinstance(type_values, list):
            type_values = [type_values]
        if not isinstance(special_values, list):
            special_values = [special_values]

        for checkbox in self.body_checkboxes:
            checkbox.setChecked(checkbox.text() in body_values)

        for checkbox in self.type_checkboxes:
            checkbox.setChecked(checkbox.text() in type_values)

        for checkbox in self.special_checkboxes:
            checkbox.setChecked(checkbox.text() in special_values)

        if keep_auto_name:
            self.update_auto_name()

    # ===== ДОБАВЛЕНИЕ АВТО: АВТОСБОРКА NAME =====
    def update_auto_name(self):
        # В режиме редактирования ничего не делаем
        if not self.auto_name_enabled:
            return

        make = self.make_combo.currentText().strip()
        model = self.model_input.text().strip()
        color = self.color_input.text().strip()

        # Собираем левую часть: Make + Model
        left_parts = []
        if make:
            left_parts.append(make)
        if model:
            left_parts.append(model)

        left_text = " ".join(left_parts).strip()

        # Финальная сборка
        if left_text and color:
            auto_name = f"{left_text} - {color}"
        elif left_text:
            auto_name = left_text
        elif color:
            auto_name = color
        else:
            auto_name = ""

        self.name_input.setText(auto_name)

    # ===== ДОБАВЛЕНИЕ/РЕДАКТИРОВАНИЕ: СОБРАТЬ ОТМЕЧЕННЫЕ ЧЕКБОКСЫ =====
    def get_checked_values(self, checkbox_list):
        return [checkbox.text() for checkbox in checkbox_list if checkbox.isChecked()]

    def find_duplicate_sku_car(self, sku_text):
        normalized_sku = str(sku_text).strip().lower()
        if not normalized_sku:
            return None

        for car in self.existing_cars:
            if not isinstance(car, dict):
                continue

            car_sku = str(car.get("sku", "")).strip().lower()
            if not car_sku or car_sku != normalized_sku:
                continue

            if self.is_edit_mode and car_sku == self.original_sku:
                continue

            return car

        return None

    def on_sku_changed(self, text):
        normalized_sku = str(text).strip()
        duplicate_car = self.find_duplicate_sku_car(text)

        if duplicate_car:
            car_name = str(duplicate_car.get("name", "")).strip()
            self.sku_status_label.setText(f'Такой SKU уже есть в базе: {car_name}')
            self.sku_status_label.setStyleSheet("color: #c62828; font-size: 11px;")
            self.sku_status_label.setVisible(True)
            self.sku_input.setStyleSheet("border: 1px solid #c62828;")
        elif normalized_sku:
            self.sku_status_label.setText("SKU свободен")
            self.sku_status_label.setStyleSheet("color: #2e7d32; font-size: 11px;")
            self.sku_status_label.setVisible(True)
            self.sku_input.setStyleSheet("border: 1px solid #2e7d32;")
        else:
            self.sku_status_label.clear()
            self.sku_status_label.setVisible(False)
            self.sku_input.setStyleSheet("")

    # ===== ДОБАВЛЕНИЕ/РЕДАКТИРОВАНИЕ: ПРОВЕРИТЬ ДАННЫЕ =====
    def validate_and_accept(self):
        name = self.name_input.text().strip()
        make = self.make_combo.currentText().strip()
        model = self.model_input.text().strip()
        color = self.color_input.text().strip()
        weight_text = self.weight_input.text().strip()
        brand = self.brand_combo.currentText().strip()
        sku = self.sku_input.text().strip()

        body_values = self.get_checked_values(self.body_checkboxes)
        type_values = self.get_checked_values(self.type_checkboxes)
        special_values = self.get_checked_values(self.special_checkboxes)

        if not name:
            QMessageBox.warning(self, "Ошибка", "Поле Name обязательно")
            return

        if not make:
            QMessageBox.warning(self, "Ошибка", "Поле Make обязательно")
            return

        if not model:
            QMessageBox.warning(self, "Ошибка", "Поле Model обязательно")
            return

        if not color:
            QMessageBox.warning(self, "Ошибка", "Поле Color обязательно")
            return

        if not weight_text:
            QMessageBox.warning(self, "Ошибка", "Поле Weight_g обязательно")
            return

        if not sku:
            QMessageBox.warning(self, "Ошибка", "Поле SKU обязательно")
            return

        duplicate_car = self.find_duplicate_sku_car(sku)
        if duplicate_car:
            duplicate_name = str(duplicate_car.get("name", "")).strip()
            QMessageBox.warning(
                self,
                "Дубликат SKU",
                f'SKU "{sku}" уже используется у машинки "{duplicate_name}"'
            )
            return

        # Вес строго в формате xx.x
        if not re.fullmatch(r"\d+\.\d", weight_text):
            QMessageBox.warning(
                self,
                "Ошибка",
                "Weight_g должен быть в формате xx.x\nНапример: 31.8"
            )
            return

        if not body_values:
            QMessageBox.warning(self, "Ошибка", "Выбери хотя бы один Body")
            return

        if not type_values:
            QMessageBox.warning(self, "Ошибка", "Выбери хотя бы один Type")
            return

                # Автоматически формируем путь к фото по SKU
        sku_clean = sku.strip()
        image_path = f"car_images/{sku_clean}.webp"

        self.result_car_data = {
            "name": name,
            "make": make,
            "model": model,
            "color": color,
            "weight_g": float(weight_text),
            "brand": brand,
            "sku": sku_clean,
            "image": image_path,
            "Body": body_values,
            "Type": type_values,
            "Special": special_values
        }

        self.accept()

    # ===== ДОБАВЛЕНИЕ/РЕДАКТИРОВАНИЕ: ПОЛУЧИТЬ ДАННЫЕ =====
    def get_car_data(self):
        return self.result_car_data
