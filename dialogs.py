import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QMessageBox,
    QListWidget, QAbstractItemView, QTextEdit, QInputDialog
)
from PyQt6.QtCore import Qt
from car_database import BODY_TOOLTIPS, TYPE_TOOLTIPS, SPECIAL_TOOLTIPS


class ReferenceListEditor(QGroupBox):
    def __init__(
        self,
        title,
        items=None,
        placeholder="",
        usage_counter=None,
        description_map=None,
        description_placeholder="",
        rename_handler=None,
        parent=None
    ):
        super().__init__(title, parent)

        self.usage_counter = usage_counter
        self.description_map = dict(description_map or {})
        self.has_descriptions = description_map is not None
        self.rename_handler = rename_handler

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.returnPressed.connect(self.add_item)

        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self.add_item)

        self.rename_btn = QPushButton("Переименовать")
        self.rename_btn.clicked.connect(self.rename_selected_item)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.currentItemChanged.connect(self.on_current_item_changed)

        self.remove_btn = QPushButton("Удалить выбранное")
        self.remove_btn.clicked.connect(self.remove_selected_items)

        self.description_label = QLabel("Описание")
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(description_placeholder)
        self.description_edit.setFixedHeight(110)
        self.description_edit.textChanged.connect(self.on_description_changed)
        self.description_edit.setEnabled(False)
        self.description_label.setVisible(self.has_descriptions)
        self.description_edit.setVisible(self.has_descriptions)

        top_row = QHBoxLayout()
        top_row.addWidget(self.input, 1)
        top_row.addWidget(self.add_btn)
        top_row.addWidget(self.rename_btn)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.description_label)
        layout.addWidget(self.description_edit)
        layout.addWidget(self.remove_btn)
        self.setLayout(layout)

        for item in items or []:
            self.append_item(item)

        self.refresh_items(select_first=True)

    def normalize_text(self, value):
        return re.sub(r"\s+", " ", str(value).strip())

    def append_item(self, value):
        text = self.normalize_text(value)
        if not text:
            return False

        existing_values = {
            self.get_raw_item_text(self.list_widget.item(index)).strip().lower()
            for index in range(self.list_widget.count())
        }
        if text.lower() in existing_values:
            return False

        self.list_widget.addItem(text)
        self.update_list_item_label(text)
        self.refresh_items(selected_name=text)
        return True

    def add_item(self):
        text = self.normalize_text(self.input.text())
        if not text:
            return

        if self.append_item(text):
            self.input.clear()
            return

        QMessageBox.information(self, "Уже существует", f'Значение "{text}" уже есть в списке')

    def remove_selected_items(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        if self.usage_counter:
            used_items = []
            for item in selected_items:
                item_text = self.get_raw_item_text(item)
                usage_count = self.usage_counter(item_text)
                if usage_count > 0:
                    used_items.append(f"{item_text} ({usage_count})")

            if used_items:
                used_items_text = ", ".join(used_items)
                reply = QMessageBox.question(
                    self,
                    "Подтверждение удаления",
                    (
                        "Выбранные значения уже используются в карточках машин: "
                        f"{used_items_text}.\n\n"
                        "Удаление уберёт их только из настроек, но не изменит уже сохранённые машины.\n\n"
                        "Продолжить?"
                    )
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        for item in selected_items:
            self.list_widget.takeItem(self.list_widget.row(item))

        self.refresh_items(select_first=True)

        if self.has_descriptions and self.list_widget.count() == 0:
            self.description_edit.blockSignals(True)
            self.description_edit.clear()
            self.description_edit.blockSignals(False)

    def get_items(self):
        return [
            self.get_raw_item_text(self.list_widget.item(index))
            for index in range(self.list_widget.count())
            if self.get_raw_item_text(self.list_widget.item(index))
        ]

    def get_description_map(self):
        return {
            item_name: self.description_map.get(item_name, "").strip()
            for item_name in self.get_items()
            if self.description_map.get(item_name, "").strip()
        }

    def get_raw_item_text(self, item):
        if not item:
            return ""

        raw_value = item.data(Qt.ItemDataRole.UserRole)
        if raw_value is None:
            return item.text().strip()

        return str(raw_value).strip()

    def find_item_by_name(self, item_name):
        normalized_name = self.normalize_text(item_name).lower()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if self.get_raw_item_text(item).lower() == normalized_name:
                return item
        return None

    def refresh_items(self, selected_name=None, select_first=False):
        item_names = self.get_items()
        item_names.sort(key=lambda value: value.lower())

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for item_name in item_names:
            self.list_widget.addItem(item_name)
            self.update_list_item_label(item_name)
        self.list_widget.blockSignals(False)

        if selected_name:
            selected_item = self.find_item_by_name(selected_name)
            if selected_item:
                self.list_widget.setCurrentItem(selected_item)
                return

        if select_first and self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        elif self.list_widget.count() == 0 and self.has_descriptions:
            self.on_current_item_changed(None, None)

    def update_list_item_label(self, item_name):
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if self.get_raw_item_text(item) != item_name:
                continue

            usage_suffix = ""
            if self.usage_counter:
                usage_count = self.usage_counter(item_name)
                usage_suffix = f" ({usage_count})"

            item.setText(f"{item_name}{usage_suffix}")
            item.setData(Qt.ItemDataRole.UserRole, item_name)
            description = self.description_map.get(item_name, "").strip()
            if description:
                item.setToolTip(description)
            else:
                item.setToolTip("")
            break

    def rename_selected_item(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "Переименование", "Сначала выбери значение из списка")
            return

        old_name = self.get_raw_item_text(current_item)
        new_name, accepted = QInputDialog.getText(
            self,
            "Переименовать",
            f'Новое имя для "{old_name}":',
            text=old_name
        )
        if not accepted:
            return

        new_name = self.normalize_text(new_name)
        if not new_name:
            QMessageBox.warning(self, "Ошибка", "Новое имя не может быть пустым")
            return

        if new_name.lower() == old_name.lower():
            if new_name != old_name:
                if self.rename_handler and not self.rename_handler(old_name, new_name):
                    return
                description = self.description_map.pop(old_name, "") if self.has_descriptions else ""
                if self.has_descriptions:
                    self.description_map[new_name] = description
                self.refresh_items(selected_name=new_name)
            return

        duplicate_item = self.find_item_by_name(new_name)
        if duplicate_item:
            QMessageBox.warning(self, "Ошибка", f'Значение "{new_name}" уже есть в списке')
            return

        if self.rename_handler and not self.rename_handler(old_name, new_name):
            return

        if self.has_descriptions:
            description = self.description_map.pop(old_name, "")
            self.description_map[new_name] = description

        current_item.setData(Qt.ItemDataRole.UserRole, new_name)
        self.refresh_items(selected_name=new_name)

    def on_current_item_changed(self, current, previous):
        if not self.has_descriptions:
            return

        self.description_edit.blockSignals(True)
        if current:
            item_name = self.get_raw_item_text(current)
            self.description_edit.setPlainText(self.description_map.get(item_name, ""))
            self.description_edit.setEnabled(True)
        else:
            self.description_edit.clear()
            self.description_edit.setEnabled(False)
        self.description_edit.blockSignals(False)

    def on_description_changed(self):
        if not self.has_descriptions:
            return

        current_item = self.list_widget.currentItem()
        if not current_item:
            return

        item_name = self.get_raw_item_text(current_item)
        self.description_map[item_name] = self.description_edit.toPlainText().strip()
        self.update_list_item_label(item_name)


class SettingsDialog(QDialog):
    def __init__(self, reference_options, existing_cars=None, parent=None):
        super().__init__(parent)

        self.reference_options = reference_options
        self.existing_cars = existing_cars or []
        self.result_reference_options = None
        self.rename_operations = {
            "brand": [],
            "Body": [],
            "Type": [],
            "Special": []
        }

        self.setWindowTitle("Настройки")
        self.setMinimumSize(880, 520)

        main_layout = QVBoxLayout()
        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(12)

        self.brand_editor = ReferenceListEditor(
            "Brand",
            self.reference_options.get("Brand", []),
            "Например: Hot Wheels",
            usage_counter=lambda value: self.count_reference_usage("brand", value),
            rename_handler=lambda old, new: self.rename_reference_value("brand", old, new)
        )
        self.body_editor = ReferenceListEditor(
            "Body",
            self.reference_options.get("Body", []),
            "Например: Coupe",
            usage_counter=lambda value: self.count_reference_usage("Body", value),
            description_map=self.reference_options.get("BodyDescriptions", {}),
            description_placeholder="Описание выбранного типа кузова",
            rename_handler=lambda old, new: self.rename_reference_value("Body", old, new)
        )
        self.type_editor = ReferenceListEditor(
            "Type",
            self.reference_options.get("Type", []),
            "Например: Supercar",
            usage_counter=lambda value: self.count_reference_usage("Type", value),
            description_map=self.reference_options.get("TypeDescriptions", {}),
            description_placeholder="Описание выбранного типа машины",
            rename_handler=lambda old, new: self.rename_reference_value("Type", old, new)
        )
        self.special_editor = ReferenceListEditor(
            "Special",
            self.reference_options.get("Special", []),
            "Например: Track-only",
            usage_counter=lambda value: self.count_reference_usage("Special", value),
            description_map=self.reference_options.get("SpecialDescriptions", {}),
            description_placeholder="Описание выбранной особенности",
            rename_handler=lambda old, new: self.rename_reference_value("Special", old, new)
        )

        lists_layout.addWidget(self.brand_editor)
        lists_layout.addWidget(self.body_editor)
        lists_layout.addWidget(self.type_editor)
        lists_layout.addWidget(self.special_editor)

        hint_label = QLabel(
            "Изменения сохраняются в cars.json. Удаление значения из этого списка не меняет уже существующие карточки машин."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #666666;")

        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        cancel_btn = QPushButton("Отмена")

        save_btn.clicked.connect(self.validate_and_accept)
        cancel_btn.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)

        main_layout.addLayout(lists_layout)
        main_layout.addWidget(hint_label)
        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)

    def validate_and_accept(self):
        updated_reference_options = dict(self.reference_options)
        updated_reference_options["Brand"] = self.brand_editor.get_items()
        updated_reference_options["Body"] = self.body_editor.get_items()
        updated_reference_options["Type"] = self.type_editor.get_items()
        updated_reference_options["Special"] = self.special_editor.get_items()
        updated_reference_options["BodyDescriptions"] = self.body_editor.get_description_map()
        updated_reference_options["TypeDescriptions"] = self.type_editor.get_description_map()
        updated_reference_options["SpecialDescriptions"] = self.special_editor.get_description_map()

        if not updated_reference_options["Brand"]:
            QMessageBox.warning(self, "Ошибка", "В списке Brand должно быть хотя бы одно значение")
            return

        if not updated_reference_options["Body"]:
            QMessageBox.warning(self, "Ошибка", "В списке Body должно быть хотя бы одно значение")
            return

        if not updated_reference_options["Type"]:
            QMessageBox.warning(self, "Ошибка", "В списке Type должно быть хотя бы одно значение")
            return

        self.result_reference_options = updated_reference_options
        self.accept()

    def get_reference_options(self):
        return self.result_reference_options

    def get_rename_operations(self):
        return self.rename_operations

    def count_reference_usage(self, field_name, value):
        normalized_value = str(value).strip().lower()
        if not normalized_value:
            return 0

        usage_count = 0
        for car in self.existing_cars:
            if not isinstance(car, dict):
                continue

            if field_name == "brand":
                brand_value = str(car.get("brand", "")).strip().lower()
                if brand_value == normalized_value:
                    usage_count += 1
                continue

            field_values = car.get(field_name, [])
            if not isinstance(field_values, list):
                field_values = [field_values]

            normalized_field_values = {
                str(item).strip().lower()
                for item in field_values
                if str(item).strip()
            }
            if normalized_value in normalized_field_values:
                usage_count += 1

        return usage_count

    def rename_reference_value(self, field_name, old_value, new_value):
        if field_name == "brand":
            for car in self.existing_cars:
                if not isinstance(car, dict):
                    continue
                brand_value = str(car.get("brand", "")).strip()
                if brand_value.lower() == old_value.lower():
                    car["brand"] = new_value
        else:
            for car in self.existing_cars:
                if not isinstance(car, dict):
                    continue
                field_values = car.get(field_name, [])
                if not isinstance(field_values, list):
                    field_values = [field_values]

                updated_values = []
                changed = False
                for item in field_values:
                    item_text = str(item).strip()
                    if item_text.lower() == old_value.lower():
                        updated_values.append(new_value)
                        changed = True
                    else:
                        updated_values.append(item_text)

                if changed:
                    deduplicated_values = []
                    seen_values = set()
                    for item in updated_values:
                        lowered_item = item.lower()
                        if lowered_item in seen_values:
                            continue
                        seen_values.add(lowered_item)
                        deduplicated_values.append(item)
                    car[field_name] = deduplicated_values

        self.rename_operations[field_name].append((old_value, new_value))
        return True


class AddCarDialog(QDialog):
    def __init__(self, reference_options, existing_cars=None, car_data=None, duplicate_source_data=None, parent=None):
        super().__init__(parent)

        self.reference_options = reference_options
        self.existing_cars = existing_cars or []
        self.result_car_data = None
        self.body_descriptions = reference_options.get("BodyDescriptions", BODY_TOOLTIPS)
        self.type_descriptions = reference_options.get("TypeDescriptions", TYPE_TOOLTIPS)
        self.special_descriptions = reference_options.get("SpecialDescriptions", SPECIAL_TOOLTIPS)
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
        self.brand_combo.setEditable(True)
        self.brand_combo.addItems(reference_options.get("Brand", []))

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
            checkbox.setToolTip(self.body_descriptions.get(item, ""))
            self.body_checkboxes.append(checkbox)
            body_layout.addWidget(checkbox)
        body_layout.addStretch()
        body_box.setLayout(body_layout)

        # ----- Type -----
        type_box = QGroupBox("Type")
        type_layout = QVBoxLayout()
        for item in self.reference_options.get("Type", []):
            checkbox = QCheckBox(item)
            checkbox.setToolTip(self.type_descriptions.get(item, ""))
            self.type_checkboxes.append(checkbox)
            type_layout.addWidget(checkbox)
        type_layout.addStretch()
        type_box.setLayout(type_layout)

        # ----- Special -----
        special_box = QGroupBox("Special")
        special_layout = QVBoxLayout()
        for item in self.reference_options.get("Special", []):
            checkbox = QCheckBox(item)
            checkbox.setToolTip(self.special_descriptions.get(item, ""))
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
        else:
            self.brand_combo.setCurrentText(brand_value)

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

        if not brand:
            QMessageBox.warning(self, "Ошибка", "Поле Brand обязательно")
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
