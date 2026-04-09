import sys
import socket
import threading
import urllib.request
import urllib.error
import json
import time
import re
import os

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTextEdit, QTableWidget,
    QTableWidgetItem, QGroupBox, QGridLayout,
    QHeaderView, QLineEdit, QMessageBox, QComboBox, QCheckBox,
    QSizePolicy, QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontDatabase, QFont, QColor, QIcon, QPixmap

from car_database import CarDatabase
from network_manager import NetworkManager
from google_sheets import GoogleSheetsManager
from results_manager import ResultsManager
from dialogs import AddCarDialog


APP_VERSION = "1.2.1"
APP_STAGE = "BETA"
APP_VERSION_LABEL = f"{APP_VERSION} {APP_STAGE}".strip()

class TimerApp(QWidget):
    esp32_message_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    finish_connection_state_signal = pyqtSignal(bool)
    start_connection_state_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        # ===== НАСТРОЙКИ: GOOGLE SHEETS =====
        self.webapp_url = "https://script.google.com/macros/s/AKfycbwC2D8vVUZTi9cpQAloBfx8_PYufiq4v_AX3dzaI_icqb7qjYCWrC8tn4_tXbcK_d5i/exec"

        font_id = QFontDatabase.addApplicationFont("DS-DIGI.TTF")
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.digital_font = QFont(font_family, 42)
        else:
            self.digital_font = QFont("Arial", 42)

        self.setWindowTitle(f"Hot Wheels Timer v{APP_VERSION_LABEL}")
        self.setWindowIcon(QIcon("timer.ico"))
        self.setGeometry(200, 200, 1100, 700)

        # ===== ИЗОБРАЖЕНИЕ МАШИНКИ =====
        self.car_image_label = QLabel("Нет фото")
        self.car_image_label.setFixedWidth(360)  # Ширина для изображения
        self.car_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.car_image_label.setScaledContents(False)  # Масштабируем вручную
        size_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.car_image_label.setSizePolicy(size_policy)
        self.car_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.car_image_label.setStyleSheet("""
            background-color: #1e1e1e;
            color: #888888;
            border: 1px solid #444444;
            border-radius: 8px;
            font-size: 14px;
        """)

        # ===== МЕНЕДЖЕРЫ =====
        self.car_db = CarDatabase()
        self.network_manager = NetworkManager()
        self.google_sheets = GoogleSheetsManager()
        # results_manager инициализируется позже, после создания self.history

        # ===== ПЕРЕМЕННЫЕ: ТЕКУЩЕЕ СОСТОЯНИЕ =====
        self.race_start_time = None
        self.current_time = None
        self.finish_time_from_module = None  # Точное время от FINISH модуля
        self.current_image_path = ""  # Текущий путь к изображению машины

        # ===== БАЗА МАШИНОК: ЗАГРУЗКА ИЗ JSON =====
        self.cars_data = self.car_db.cars_data
        self.reference_options = self.car_db.reference_options

# Справочники фильтров берём из cars.json
        self.body_options = ["All"] + self.reference_options.get("Body", [])
        self.type_options = ["All"] + self.reference_options.get("Type", [])
        self.special_options = ["All"] + self.reference_options.get("Special", [])

        # Make и Brand собираем автоматически из базы
        make_values = sorted({
            str(car.get("make", "")).strip()
            for car in self.cars_data
            if isinstance(car, dict) and str(car.get("make", "")).strip()
        }, key=lambda x: x.lower())

        brand_values = sorted({
            str(car.get("brand", "")).strip()
            for car in self.cars_data
            if isinstance(car, dict) and str(car.get("brand", "")).strip()
        }, key=lambda x: x.lower())

        self.make_options = ["All"] + make_values
        self.brand_options = ["All"] + brand_values

        # Полный список имён машин
        self.car_names = [
            car.get("name", "").strip()
            for car in self.cars_data
            if isinstance(car, dict) and car.get("name", "").strip()
        ]

        # Сортируем по алфавиту
        self.car_names = sorted(self.car_names, key=lambda x: x.lower())

        # Полный список имен машин
        self.car_names = [
            car.get("name", "").strip()
            for car in self.cars_data
            if isinstance(car, dict) and car.get("name", "").strip()
        ]

        # Сортируем по алфавиту
        self.car_names = sorted(self.car_names, key=lambda x: x.lower())

        # ===== ТАЙМЕР: ЖИВОЕ ОБНОВЛЕНИЕ ВРЕМЕНИ =====
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.update_live_timer)

        # ===== СИГНАЛЫ =====
        self.network_manager.set_signals(
            self.finish_connection_state_signal,
            self.start_connection_state_signal,
            self.esp32_message_signal,
            self.log_signal
        )
        self.esp32_message_signal.connect(self.handle_esp32_message)
        self.log_signal.connect(self.log)
        self.finish_connection_state_signal.connect(self.update_finish_connection_state)
        self.start_connection_state_signal.connect(self.update_start_connection_state)

        # ===== ГЛАВНЫЙ LAYOUT =====
        main_layout = QHBoxLayout()

        # Левая часть: изображение машинки
        main_layout.addWidget(self.car_image_label)

        # Правая часть: остальной интерфейс
        right_layout = QVBoxLayout()
        modules_box = QGroupBox("Состояние модулей")
        modules_layout = QGridLayout()

        self.start_indicator = QLabel("●")
        self.start_indicator.setStyleSheet("font-size: 20px; color: red;")
        self.start_status = QLabel("Стартовый модуль: Offline")

        self.finish_indicator = QLabel("●")
        self.finish_indicator.setStyleSheet("font-size: 20px; color: red;")
        self.finish_status = QLabel("Финишный модуль: Offline")

        self.start_beam = QLabel("Стартовый луч: Locked")
        self.finish_beam = QLabel("Финишный луч: Locked")

        self.start_temp_title = QLabel("Температура старта:")
        self.start_temp_label = QLabel("--.- °C")
        self.finish_temp_title = QLabel("Температура финиша:")
        self.finish_temp_label = QLabel("--.- °C")

        modules_layout.addWidget(self.start_indicator, 0, 0)
        modules_layout.addWidget(self.start_status, 0, 1)
        modules_layout.addWidget(self.finish_indicator, 0, 2)
        modules_layout.addWidget(self.finish_status, 0, 3)

        modules_layout.addWidget(self.start_beam, 1, 1)
        modules_layout.addWidget(self.finish_beam, 1, 3)

        modules_layout.addWidget(self.start_temp_title, 2, 0)
        modules_layout.addWidget(self.start_temp_label, 2, 1)
        modules_layout.addWidget(self.finish_temp_title, 2, 2)
        modules_layout.addWidget(self.finish_temp_label, 2, 3)

        modules_box.setLayout(modules_layout)

        # ===== БЛОК: ТЕКУЩИЙ ЗАЕЗД =====
        current_box = QGroupBox("Текущий заезд")
        current_layout = QVBoxLayout()

        self.mode_label = QLabel("Режим системы: READY")

        self.time_display = QLabel("0.000")
        self.time_display.setFont(self.digital_font)
        self.time_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_ready_style()

        self.time_label = QLabel("Время: 0.000")

        # ===== БЛОК: АВТО И INFORMATION =====
        car_and_info_layout = QHBoxLayout()

        # Блок фото
        photo_block_layout = QVBoxLayout()
        self.photo_block_title = QLabel("Photo")
        self.photo_block_title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.car_photo_label = QLabel("Нет фото")
        self.car_photo_label.setFixedSize(240, 180)  # 4:3
        self.car_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.car_photo_label.setStyleSheet("""
            background-color: #1e1e1e;
            color: #888888;
            border: 1px solid #444444;
            border-radius: 8px;
            font-size: 14px;
        """)

        photo_block_layout.addWidget(self.photo_block_title)
        photo_block_layout.addWidget(self.car_photo_label)
        photo_block_layout.addStretch()

        # Левый блок
        car_block_layout = QVBoxLayout()
        self.car_block_title = QLabel("Car (0)")
        self.car_block_title.setStyleSheet("font-size: 16px; font-weight: bold;")

        car_panel_width = 454
        combo_action_btn_width = 34
        combo_row_spacing = 6
        combo_field_width = car_panel_width - (combo_action_btn_width * 2) - (combo_row_spacing * 2)
        search_row_spacing = 10
        name_search_width = 332
        sku_search_width = car_panel_width - name_search_width - search_row_spacing
        filter_row_spacing = 10
        filter_field_widths = [145, 144, 145]

        self.car_combo = QComboBox()
        self.car_combo.addItem("— Не выбрано —")
        self.car_combo.addItems(self.car_names)
        self.car_combo.setFixedWidth(combo_field_width)
        self.car_combo.currentIndexChanged.connect(self.on_car_selection_changed)

        self.edit_car_btn = QPushButton("✎")
        self.edit_car_btn.setFixedSize(34, 34)
        self.edit_car_btn.setToolTip("Редактировать выбранную машинку")
        self.edit_car_btn.clicked.connect(self.open_edit_car_dialog)

        self.duplicate_car_btn = QPushButton("⧉")
        self.duplicate_car_btn.setFixedSize(34, 34)
        self.duplicate_car_btn.setToolTip("Дублировать выбранную машинку")
        self.duplicate_car_btn.clicked.connect(self.open_duplicate_car_dialog)

        self.car_search_input = QLineEdit()
        self.car_search_input.setPlaceholderText("Поиск авто по названию")
        self.car_search_input.setFixedWidth(name_search_width)
        self.car_search_input.textChanged.connect(self.apply_car_filters)

        self.car_sku_search_input = QLineEdit()
        self.car_sku_search_input.setPlaceholderText("SKU")
        self.car_sku_search_input.setFixedWidth(sku_search_width)
        self.car_sku_search_input.textChanged.connect(self.apply_car_filters)

        self.add_car_btn = QPushButton("Создать новое авто")
        self.add_car_btn.setFixedWidth(car_panel_width)
        self.add_car_btn.clicked.connect(self.open_add_car_dialog)

        car_block_layout.addWidget(self.car_block_title)

        # ===== ФИЛЬТРЫ МАШИНОК =====
        filters_main_layout = QVBoxLayout()
        filters_main_layout.setSpacing(6)
        filters_main_layout.setContentsMargins(0, 0, 0, 0)

        filters_top_row = QHBoxLayout()
        filters_top_row.setSpacing(filter_row_spacing)
        filters_top_row.setContentsMargins(0, 0, 0, 0)

        filters_bottom_row = QHBoxLayout()
        filters_bottom_row.setSpacing(filter_row_spacing)
        filters_bottom_row.setContentsMargins(0, 0, 0, 0)

        # ----- Make -----
        make_filter_block = QVBoxLayout()
        make_filter_block.setSpacing(2)

        self.make_filter_title = QLabel("Make")
        self.make_filter_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")

        self.make_filter = QComboBox()
        self.make_filter.addItems(self.make_options)
        self.make_filter.setFixedWidth(filter_field_widths[0])

        make_filter_block.addWidget(self.make_filter_title)
        make_filter_block.addWidget(self.make_filter)

        # ----- Type -----
        type_filter_block = QVBoxLayout()
        type_filter_block.setSpacing(2)

        self.type_filter_title = QLabel("Type")
        self.type_filter_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")

        self.type_filter = QComboBox()
        self.type_filter.addItems(self.type_options)
        self.type_filter.setFixedWidth(filter_field_widths[1])

        type_filter_block.addWidget(self.type_filter_title)
        type_filter_block.addWidget(self.type_filter)

        # ----- Body -----
        body_filter_block = QVBoxLayout()
        body_filter_block.setSpacing(2)

        self.body_filter_title = QLabel("Body")
        self.body_filter_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")

        self.body_filter = QComboBox()
        self.body_filter.addItems(self.body_options)
        self.body_filter.setFixedWidth(filter_field_widths[2])

        body_filter_block.addWidget(self.body_filter_title)
        body_filter_block.addWidget(self.body_filter)

        # ----- Special -----
        special_filter_block = QVBoxLayout()
        special_filter_block.setSpacing(2)

        self.special_filter_title = QLabel("Special")
        self.special_filter_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")

        self.special_filter = QComboBox()
        self.special_filter.addItems(self.special_options)
        self.special_filter.setFixedWidth(filter_field_widths[0])

        special_filter_block.addWidget(self.special_filter_title)
        special_filter_block.addWidget(self.special_filter)

        # ----- Brand -----
        brand_filter_block = QVBoxLayout()
        brand_filter_block.setSpacing(2)

        self.brand_filter_title = QLabel("Brand")
        self.brand_filter_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")

        self.brand_filter = QComboBox()
        self.brand_filter.addItems(self.brand_options)
        self.brand_filter.setFixedWidth(filter_field_widths[1])

        brand_filter_block.addWidget(self.brand_filter_title)
        brand_filter_block.addWidget(self.brand_filter)

        # ----- Кнопка очистки -----
        clear_filters_block = QVBoxLayout()
        clear_filters_block.setSpacing(2)

        self.clear_filters_title = QLabel(" ")
        self.clear_filters_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")

        self.clear_filters_btn = QPushButton("Очистить")
        self.clear_filters_btn.setFixedWidth(filter_field_widths[2])

        clear_filters_block.addWidget(self.clear_filters_title)
        clear_filters_block.addWidget(self.clear_filters_btn)

        # Подключаем сигналы фильтров после их создания
        self.make_filter.currentIndexChanged.connect(self.apply_car_filters)
        self.type_filter.currentIndexChanged.connect(self.apply_car_filters)
        self.body_filter.currentIndexChanged.connect(self.apply_car_filters)
        self.special_filter.currentIndexChanged.connect(self.apply_car_filters)
        self.brand_filter.currentIndexChanged.connect(self.apply_car_filters)

        # Кнопка сброса фильтров
        self.clear_filters_btn.clicked.connect(self.reset_car_filters)

        # Верхний ряд
        filters_top_row.addLayout(make_filter_block)
        filters_top_row.addLayout(type_filter_block)
        filters_top_row.addLayout(body_filter_block)

        # Нижний ряд
        filters_bottom_row.addLayout(special_filter_block)
        filters_bottom_row.addLayout(brand_filter_block)
        filters_bottom_row.addLayout(clear_filters_block)

        filters_main_layout.addLayout(filters_top_row)
        filters_main_layout.addLayout(filters_bottom_row)

        car_block_layout.addLayout(filters_main_layout)
        combo_row_layout = QHBoxLayout()
        combo_row_layout.setSpacing(combo_row_spacing)
        combo_row_layout.setContentsMargins(0, 0, 0, 0)
        combo_row_layout.addWidget(self.car_combo)
        combo_row_layout.addWidget(self.edit_car_btn)
        combo_row_layout.addWidget(self.duplicate_car_btn)

        car_block_layout.addLayout(combo_row_layout)
        search_row_layout = QHBoxLayout()
        search_row_layout.setSpacing(search_row_spacing)
        search_row_layout.setContentsMargins(0, 0, 0, 0)
        search_row_layout.addWidget(self.car_search_input)
        search_row_layout.addWidget(self.car_sku_search_input)

        car_block_layout.addLayout(search_row_layout)
        car_block_layout.addWidget(self.add_car_btn)
        car_block_layout.addStretch()

        # Правый блок
        info_block_layout = QVBoxLayout()
        self.info_block_title = QLabel("Information")
        self.info_block_title.setStyleSheet("font-size: 16px; font-weight: bold;")

        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(28)
        info_grid.setVerticalSpacing(14)  # меньше зазор между заголовком и значением (было 18)

        # Фиксируем пропорции ширины колонок блока Information
        # Числа работают как относительная ширина
        # Три одинаковые колонки
        info_grid.setColumnStretch(0, 1)  # Make и Weight
        info_grid.setColumnStretch(1, 1)  # Model и SKU
        info_grid.setColumnStretch(2, 1)  # Color и Brand

        # ===== INFORMATION: ЯЧЕЙКИ =====
        self.make_title = QLabel("Make")
        self.make_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")
        self.make_value = QLabel("—")
        self.make_value.setWordWrap(False)
        self.make_value.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.model_title = QLabel("Model")
        self.model_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")
        self.model_value = QLabel("—")
        self.model_value.setWordWrap(False)
        self.model_value.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.color_title = QLabel("Color")
        self.color_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")
        self.color_value = QLabel("—")
        self.color_value.setWordWrap(False)
        self.color_value.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.weight_title = QLabel("Weight")
        self.weight_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")
        self.weight_value = QLabel("—")
        self.weight_value.setWordWrap(False)
        self.weight_value.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.sku_title = QLabel("SKU")
        self.sku_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")
        self.sku_value = QLabel("—")
        self.sku_value.setWordWrap(False)
        self.sku_value.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.brand_title = QLabel("Brand")
        self.brand_title.setStyleSheet("font-size: 11px; color: #b0b0b0;")
        self.brand_value = QLabel("—")
        self.brand_value.setWordWrap(False)
        self.brand_value.setStyleSheet("font-size: 18px; font-weight: bold;")

        # ===== INFORMATION: КОЛОНКИ =====
        # Каждая колонка имеет фиксированную высоту.
        # За счет addStretch() заголовок опускается ниже,
        # а значение остается внизу колонки.
        make_cell = QWidget()
        make_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        make_layout = QVBoxLayout(make_cell)
        make_layout.setContentsMargins(0, 0, 0, 0)
        make_layout.setSpacing(2)
        make_layout.addStretch()
        make_layout.addWidget(self.make_title)
        make_layout.addWidget(self.make_value)
        make_cell.setFixedHeight(44)

        model_cell = QWidget()
        model_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        model_layout = QVBoxLayout(model_cell)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(2)
        model_layout.addStretch()
        model_layout.addWidget(self.model_title)
        model_layout.addWidget(self.model_value)
        model_cell.setFixedHeight(44)

        color_cell = QWidget()
        color_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        color_layout = QVBoxLayout(color_cell)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(2)
        color_layout.addStretch()
        color_layout.addWidget(self.color_title)
        color_layout.addWidget(self.color_value)
        color_cell.setFixedHeight(44)

        weight_cell = QWidget()
        weight_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        weight_layout = QVBoxLayout(weight_cell)
        weight_layout.setContentsMargins(0, 0, 0, 0)
        weight_layout.setSpacing(2)
        weight_layout.addStretch()
        weight_layout.addWidget(self.weight_title)
        weight_layout.addWidget(self.weight_value)
        weight_cell.setFixedHeight(44)

        wheel_cell = QWidget()
        wheel_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        wheel_layout = QVBoxLayout(wheel_cell)
        wheel_layout.setContentsMargins(0, 0, 0, 0)
        wheel_layout.setSpacing(2)
        wheel_layout.addStretch()
        wheel_layout.addWidget(self.sku_title)
        wheel_layout.addWidget(self.sku_value)
        wheel_cell.setFixedHeight(44)

        brand_cell = QWidget()
        brand_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        brand_layout = QVBoxLayout(brand_cell)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(2)
        brand_layout.addStretch()
        brand_layout.addWidget(self.brand_title)
        brand_layout.addWidget(self.brand_value)
        brand_cell.setFixedHeight(44)

        info_grid.addWidget(make_cell, 0, 0)
        info_grid.addWidget(model_cell, 0, 1)
        info_grid.addWidget(color_cell, 0, 2)

        info_grid.addWidget(weight_cell, 1, 0)
        info_grid.addWidget(wheel_cell, 1, 1)
        info_grid.addWidget(brand_cell, 1, 2)

        info_block_layout.addWidget(self.info_block_title)
        info_block_layout.addLayout(info_grid)
        info_block_layout.addStretch()

        car_and_info_layout.addSpacing(24)
        car_and_info_layout.addLayout(car_block_layout)
        car_and_info_layout.addSpacing(40)
        car_and_info_layout.addLayout(info_block_layout)
        car_and_info_layout.addStretch()

        # ===== БЛОК: GOOGLE SHEETS =====
        self.export_google_btn = QPushButton("Отправить в Google Sheets")
        self.export_google_btn.clicked.connect(self.export_all_results)

        # Статус оставляем в коде, но не показываем в интерфейсе
        self.sheets_label = QLabel("Google Sheets: ожидание")
        self.sheets_label.hide()


        current_layout.addWidget(self.mode_label)
        current_layout.addWidget(self.time_display)
        current_layout.addWidget(self.time_label)
        current_layout.addLayout(car_and_info_layout)

        current_box.setLayout(current_layout)

        # ===== БЛОК: КНОПКИ УПРАВЛЕНИЯ =====
        buttons_box = QGroupBox("Управление")
        buttons_layout = QHBoxLayout()

        self.reset_btn = QPushButton("Обнулить")
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setEnabled(False)
        self.delete_btn = QPushButton("Удалить запись")
        self.clear_table_btn = QPushButton("Очистить таблицу")
        self.about_btn = QPushButton("О программе")

        self.save_btn.clicked.connect(self.save_time)
        self.reset_btn.clicked.connect(self.reset_race)
        self.delete_btn.clicked.connect(self.delete_race)
        self.clear_table_btn.clicked.connect(self.clear_results_table)
        self.about_btn.clicked.connect(self.show_about)

        buttons_layout.addWidget(self.reset_btn)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.delete_btn)
        buttons_layout.addWidget(self.clear_table_btn)

        buttons_box.setLayout(buttons_layout)

        # ===== НИЖНИЙ БЛОК =====
        bottom_layout = QHBoxLayout()

        logs_box = QGroupBox("Логи событий")
        logs_layout = QVBoxLayout()
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.append(f"Программа запущена. Версия {APP_VERSION_LABEL}")

        logs_layout.addWidget(self.logs)
        logs_layout.addWidget(self.about_btn)  # кнопка под логами

        logs_box.setLayout(logs_layout)

        history_box = QGroupBox("Таблица результатов")
        history_layout = QVBoxLayout()

        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(["№", "Car", "Время", "Gap", "Sheets"])
        self.history.verticalHeader().setVisible(False)
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        header = self.history.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.history.setColumnWidth(1, 180)
        self.history.setColumnWidth(2, 130)
        self.history.setColumnWidth(3, 130)
        self.history.setColumnWidth(4, 80)

        # ===== МЕНЕДЖЕРЫ: ДОПОЛНИТЕЛЬНАЯ ИНИЦИАЛИЗАЦИЯ =====
        self.results_manager = ResultsManager(self.history)
        
        # Загружаем сохраненные результаты при запуске
        if self.results_manager.load_from_file("results_data.json"):
            self.log("Результаты загружены из файла")
        else:
            self.log("Новая сессия - результаты еще не сохранены")

        history_layout.addWidget(self.history)
        history_layout.addWidget(self.export_google_btn)  # кнопка под таблицей
        history_box.setLayout(history_layout)

        bottom_layout.addWidget(logs_box, 1)
        bottom_layout.addWidget(history_box, 1)

        right_layout.addWidget(modules_box)
        right_layout.addWidget(current_box)
        right_layout.addWidget(buttons_box)
        right_layout.addLayout(bottom_layout)

        main_layout.addLayout(right_layout)

        self.setLayout(main_layout)

        # ===== ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ =====
        self.update_google_status_label()
        self.apply_car_filters()
        self.update_car_info_panel()

        # ===== ЗАПУСК СЕТЕВЫХ ПОТОКОВ =====
        self.network_manager.start_network()
        self.network_manager.start_start_network()

    # ===== БАЗА МАШИНОК: ПЕРЕЗАГРУЗИТЬ БАЗУ И ФИЛЬТРЫ =====
    def reload_cars_data_and_filters(self, selected_car_name=""):
        # Перечитываем cars.json
        self.car_db.reload_data()
        self.cars_data = self.car_db.cars_data
        self.reference_options = self.car_db.reference_options

        # Обновляем справочники фильтров
        self.body_options = ["All"] + self.reference_options.get("Body", [])
        self.type_options = ["All"] + self.reference_options.get("Type", [])
        self.special_options = ["All"] + self.reference_options.get("Special", [])

        make_values = sorted({
            str(car.get("make", "")).strip()
            for car in self.cars_data
            if isinstance(car, dict) and str(car.get("make", "")).strip()
        }, key=lambda x: x.lower())

        brand_values = sorted({
            str(car.get("brand", "")).strip()
            for car in self.cars_data
            if isinstance(car, dict) and str(car.get("brand", "")).strip()
        }, key=lambda x: x.lower())

        self.make_options = ["All"] + make_values
        self.brand_options = ["All"] + brand_values

        self.car_names = [
            car.get("name", "").strip()
            for car in self.cars_data
            if isinstance(car, dict) and car.get("name", "").strip()
        ]
        self.car_names = sorted(self.car_names, key=lambda x: x.lower())

        # Перезаполняем фильтры
        self.make_filter.blockSignals(True)
        self.type_filter.blockSignals(True)
        self.body_filter.blockSignals(True)
        self.special_filter.blockSignals(True)
        self.brand_filter.blockSignals(True)

        self.make_filter.clear()
        self.make_filter.addItems(self.make_options)
        self.make_filter.setCurrentIndex(0)

        self.type_filter.clear()
        self.type_filter.addItems(self.type_options)
        self.type_filter.setCurrentIndex(0)

        self.body_filter.clear()
        self.body_filter.addItems(self.body_options)
        self.body_filter.setCurrentIndex(0)

        self.special_filter.clear()
        self.special_filter.addItems(self.special_options)
        self.special_filter.setCurrentIndex(0)

        self.brand_filter.clear()
        self.brand_filter.addItems(self.brand_options)
        self.brand_filter.setCurrentIndex(0)

        self.make_filter.blockSignals(False)
        self.type_filter.blockSignals(False)
        self.body_filter.blockSignals(False)
        self.special_filter.blockSignals(False)
        self.brand_filter.blockSignals(False)

        # Очищаем поиск и пересобираем список машин
        self.car_search_input.clear()
        self.car_sku_search_input.clear()
        self.apply_car_filters()

        # Если передано имя новой машинки — выбираем её
        if selected_car_name:
            index = self.car_combo.findText(selected_car_name)
            if index >= 0:
                self.car_combo.setCurrentIndex(index)

        self.update_car_info_panel()

    # ===== СЛУЖЕБНАЯ ФУНКЦИЯ: ЛОГ =====
    def resizeEvent(self, event):
        """Пересчитываем размер изображения при изменении размера окна"""
        super().resizeEvent(event)
        if self.car_image_label.pixmap() and not self.car_image_label.pixmap().isNull():
            self.update_car_photo_panel(self.current_image_path if hasattr(self, 'current_image_path') else "")
    
    def log(self, text):
        self.logs.append(text)

    # ===== СЛУЖЕБНАЯ ФУНКЦИЯ: СОСТОЯНИЕ FINISH =====
    def update_finish_connection_state(self, online):
        if online:
            self.finish_status.setText("Финишный модуль: Online")
            self.finish_indicator.setStyleSheet("font-size: 20px; color: lime;")
        else:
            self.finish_status.setText("Финишный модуль: Offline")
            self.finish_indicator.setStyleSheet("font-size: 20px; color: red;")

    # ===== СЛУЖЕБНАЯ ФУНКЦИЯ: СОСТОЯНИЕ START =====
    def update_start_connection_state(self, online):
        if online:
            self.start_status.setText("Стартовый модуль: Online")
            self.start_indicator.setStyleSheet("font-size: 20px; color: lime;")
        else:
            self.start_status.setText("Стартовый модуль: Offline")
            self.start_indicator.setStyleSheet("font-size: 20px; color: red;")

    # ===== ФОТО: ПОКАЗАТЬ ЗАГЛУШКУ =====
    def set_default_car_photo(self):
        self.car_image_label.clear()
        self.car_image_label.setText("Нет фото")
        self.car_image_label.setStyleSheet("""
            background-color: #1e1e1e;
            color: #888888;
            border: 1px solid #444444;
            border-radius: 8px;
            font-size: 14px;
        """)

    # ===== ФОТО: ОБНОВИТЬ ИЗОБРАЖЕНИЕ МАШИНКИ =====
    def update_car_photo_panel(self, image_path):
        image_path = str(image_path).strip()
        self.current_image_path = image_path  # Сохраняем для использования при resizeEvent

        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)

            if not pixmap.isNull():
                # Масштабируем под текущий размер QLabel с сохранением пропорций (формат 2:3)
                label_width = self.car_image_label.width()
                label_height = self.car_image_label.height()
                
                scaled_pixmap = pixmap.scaled(
                    label_width,
                    label_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                self.car_image_label.setText("")
                self.car_image_label.setPixmap(scaled_pixmap)
                self.car_image_label.setStyleSheet("""
                    background-color: #1e1e1e;
                    border: 1px solid #444444;
                    border-radius: 8px;
                """)
                return

        self.set_default_car_photo()

    # ===== СЛУЖЕБНАЯ ФУНКЦИЯ: СТАТУС GOOGLE =====
    def update_google_status_label(self):
        if self.current_time is None:
            self.sheets_label.setText("Google Sheets: ожидание")
        else:
            self.sheets_label.setText("Google Sheets: готово к выгрузке")

    # ===== СТИЛИ: READY =====
    def set_ready_style(self):
        self.time_display.setStyleSheet("""
            background-color: #2b2b2b;
            color: #00ff66;
            font-size: 72px;
            font-weight: bold;
            padding: 14px;
            border: 2px solid #444;
            border-radius: 8px;
        """)

    # ===== СТИЛИ: RACE =====
    def set_race_style(self):
        self.time_display.setStyleSheet("""
            background-color: #2b2b2b;
            color: #ffd54a;
            font-size: 72px;
            font-weight: bold;
            padding: 14px;
            border: 2px solid #444;
            border-radius: 8px;
        """)

    # ===== СТИЛИ: FINISH =====
    def set_finish_style(self):
        self.time_display.setStyleSheet("""
            background-color: #2b2b2b;
            color: #00ff66;
            font-size: 72px;
            font-weight: bold;
            padding: 14px;
            border: 2px solid #444;
            border-radius: 8px;
        """)

    # ===== ВИЗУАЛ: ВСПЫШКА ПОСЛЕ ФИНИША =====
    def flash_finish(self):
        self.time_display.setStyleSheet("""
            background-color: #2b2b2b;
            color: #ffffff;
            font-size: 72px;
            font-weight: bold;
            padding: 14px;
            border: 2px solid #00ff66;
            border-radius: 8px;
        """)
        QTimer.singleShot(800, self.set_finish_style)

    # ===== ТАЙМЕР: ЖИВОЕ ОБНОВЛЕНИЕ =====
    def update_live_timer(self):
        if self.race_start_time is None:
            return
        elapsed = time.time() - self.race_start_time
        self.time_display.setText(f"{elapsed:.3f}")

    # ===== АВТО: ПОИСК В БАЗЕ =====
    def find_car_in_database(self, car_name):
        search_name = car_name.strip().lower()
        for car in self.cars_data:
            db_name = str(car.get("name", "")).strip().lower()
            if db_name == search_name:
                return car
        return None
    
    # ===== АВТО: ПОЛУЧИТЬ SKU И BRAND ПО ИМЕНИ =====
    def get_car_extra_data(self, car_name):
        car_data = self.car_db.find_car_in_database(car_name)

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

    # ===== АВТО: ИТОГОВОЕ ИМЯ =====
    def resolve_car_name(self):
        combo_text = self.car_combo.currentText().strip()

        if combo_text and combo_text != "— Не выбрано —":
            return combo_text
        return "Unknown Car"
    
    # ===== АВТО: ОБНОВИТЬ СЧЁТЧИК В ЗАГОЛОВКЕ =====
    def update_car_count_label(self, count):
        self.car_block_title.setText(f"Car ({count})")
    
    # ===== АВТО: ПРИМЕНИТЬ ФИЛЬТРЫ =====
    def apply_car_filters(self):
        selected_make = self.make_filter.currentText()
        selected_type = self.type_filter.currentText()
        selected_body = self.body_filter.currentText()
        selected_special = self.special_filter.currentText()
        selected_brand = self.brand_filter.currentText()
        search_text = self.car_search_input.text().strip().lower()
        sku_search_text = self.car_sku_search_input.text().strip().lower()

        filtered_names = []

        for car in self.cars_data:
            car_name = str(car.get("name", "")).strip()
            if not car_name:
                continue

            car_make = str(car.get("make", "")).strip()
            car_brand = str(car.get("brand", "")).strip()
            car_sku = str(car.get("sku", "")).strip().lower()
            car_body = car.get("Body", [])
            car_type = car.get("Type", [])
            car_special = car.get("Special", [])

            # Если в JSON вдруг записана строка, а не список — превращаем в список
            if not isinstance(car_body, list):
                car_body = [car_body]
            if not isinstance(car_type, list):
                car_type = [car_type]
            if not isinstance(car_special, list):
                car_special = [car_special]

            # Проверка Make
            if selected_make != "All" and selected_make != car_make:
                continue

            # Проверка Type
            if selected_type != "All" and selected_type not in car_type:
                continue

            # Проверка Body
            if selected_body != "All" and selected_body not in car_body:
                continue

            # Проверка Special
            if selected_special != "All" and selected_special not in car_special:
                continue

            # Проверка Brand
            if selected_brand != "All" and selected_brand != car_brand:
                continue

            # Поиск по части названия
            if search_text and search_text not in car_name.lower():
                continue

            # Поиск по части SKU
            if sku_search_text and sku_search_text not in car_sku:
                continue

            filtered_names.append(car_name)

        filtered_names = sorted(filtered_names, key=lambda x: x.lower())
        self.update_car_count_label(len(filtered_names))

        current_car_name = self.car_combo.currentText()

        self.car_combo.blockSignals(True)
        self.car_combo.clear()
        self.car_combo.addItem("— Не выбрано —")
        self.car_combo.addItems(filtered_names)

        if current_car_name in filtered_names:
            self.car_combo.setCurrentText(current_car_name)
        else:
            self.car_combo.setCurrentIndex(0)

        self.car_combo.blockSignals(False)

        self.update_car_info_panel()

    # ===== АВТО: СБРОСИТЬ ФИЛЬТРЫ =====
    def reset_car_filters(self):
        self.make_filter.blockSignals(True)
        self.type_filter.blockSignals(True)
        self.body_filter.blockSignals(True)
        self.special_filter.blockSignals(True)
        self.brand_filter.blockSignals(True)

        self.make_filter.setCurrentIndex(0)
        self.type_filter.setCurrentIndex(0)
        self.body_filter.setCurrentIndex(0)
        self.special_filter.setCurrentIndex(0)
        self.brand_filter.setCurrentIndex(0)

        self.make_filter.blockSignals(False)
        self.type_filter.blockSignals(False)
        self.body_filter.blockSignals(False)
        self.special_filter.blockSignals(False)
        self.brand_filter.blockSignals(False)

        self.car_search_input.clear()
        self.car_sku_search_input.clear()
        self.apply_car_filters()

    # ===== АВТО: СОБЫТИЕ ВЫБОРА =====
    def on_car_selection_changed(self):
        self.update_car_info_panel()

    # ===== АВТО: ОТКРЫТЬ ОКНО ДОБАВЛЕНИЯ =====
    def open_add_car_dialog(self):
        dialog = AddCarDialog(
            reference_options=self.reference_options,
            existing_cars=self.car_db.cars_data,
            parent=self
        )

        if dialog.exec():
            new_car_data = dialog.get_car_data()
            if not new_car_data:
                return

            if not self.car_db.save_new_car_to_database(new_car_data):
                return

            self.reload_cars_data_and_filters(new_car_data["name"])
            self.log(f'Новая машинка добавлена в базу: {new_car_data["name"]}')
            QMessageBox.information(
                self,
                "Готово",
                f'Машинка "{new_car_data["name"]}" добавлена в базу'
            )

    # ===== АВТО: ОТКРЫТЬ ОКНО ДУБЛИРОВАНИЯ =====
    def open_duplicate_car_dialog(self):
        selected_name = self.car_combo.currentText().strip()

        if not selected_name or selected_name == "— Не выбрано —":
            QMessageBox.information(self, "Дублирование", "Сначала выбери машинку из списка")
            return

        car_data = self.car_db.find_car_in_database(selected_name)
        if not car_data:
            QMessageBox.warning(self, "Ошибка", "Не удалось найти машинку в базе")
            return

        dialog = AddCarDialog(
            reference_options=self.reference_options,
            existing_cars=self.car_db.cars_data,
            duplicate_source_data=car_data,
            parent=self
        )

        if dialog.exec():
            new_car_data = dialog.get_car_data()
            if not new_car_data:
                return

            if not self.car_db.save_new_car_to_database(new_car_data):
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Не удалось сохранить дубликат. Проверь, что Name и SKU уникальны."
                )
                return

            self.reload_cars_data_and_filters(new_car_data["name"])
            self.log(f'Создан дубликат машинки: {new_car_data["name"]}')
            QMessageBox.information(
                self,
                "Готово",
                f'Дубликат машинки "{new_car_data["name"]}" добавлен в базу'
            )

    # ===== АВТО: ОТКРЫТЬ ОКНО РЕДАКТИРОВАНИЯ =====
    def open_edit_car_dialog(self):
        selected_name = self.car_combo.currentText().strip()

        if not selected_name or selected_name == "— Не выбрано —":
            QMessageBox.information(self, "Редактирование", "Сначала выбери машинку из списка")
            return

        car_data = self.car_db.find_car_in_database(selected_name)
        if not car_data:
            QMessageBox.warning(self, "Ошибка", "Не удалось найти машинку в базе")
            return

        dialog = AddCarDialog(
            reference_options=self.reference_options,
            existing_cars=self.car_db.cars_data,
            car_data=car_data,
            parent=self
        )

        if dialog.exec():
            updated_car_data = dialog.get_car_data()
            if not updated_car_data:
                return

            if not self.car_db.save_edited_car_to_database(selected_name, updated_car_data):
                return

            self.results_manager.update_result_names_after_edit(selected_name, updated_car_data["name"])
            self.reload_cars_data_and_filters(updated_car_data["name"])

            self.log(f'Машинка обновлена: {updated_car_data["name"]}')
            QMessageBox.information(
                self,
                "Готово",
                f'Машинка "{updated_car_data["name"]}" успешно обновлена'
            )

    # ===== АВТО: ОБНОВИТЬ INFORMATION =====
    def update_car_info_panel(self):
        selected_name = self.resolve_car_name()
        car_data = self.car_db.find_car_in_database(selected_name)

        if car_data:
            make = car_data.get("make", "—")
            model = car_data.get("model", "—")
            color = car_data.get("color", "—")
            weight = car_data.get("weight_g", "—")
            brand = car_data.get("brand", "—")

            # SKU: если пустой, показываем прочерк
            sku = car_data.get("sku", "—")
            sku_text = str(sku).strip() if str(sku).strip() else "—"
            image_path = car_data.get("image", "")

            # Вес: если есть значение, добавляем g
            weight_text = f"{weight} g" if weight != "—" else "—"
        else:
            make = "—"
            model = "—" if selected_name == "Unknown Car" else selected_name
            color = "—"
            weight_text = "—"
            sku_text = "—"
            brand = "—"
            image_path = ""

        self.make_value.setText(str(make))
        self.model_value.setText(str(model))
        self.color_value.setText(str(color))
        self.weight_value.setText(str(weight_text))
        self.sku_value.setText(str(sku_text))
        self.brand_value.setText(str(brand))
        self.update_car_photo_panel(image_path)

    # ===== ТАБЛИЦА РЕЗУЛЬТАТОВ: ПОДПИСЬ ТОП-3 =====
    # ===== БЕЗОПАСНОСТЬ: ПОДТВЕРЖДЕНИЕ ПЕРЕЗАПИСИ =====
    def confirm_overwrite_existing_car(self, car_name):
        existing_index = self.results_manager.find_result_index_by_car(car_name)

        if existing_index < 0:
            return True

        old_time = self.results_manager.results_data[existing_index]["time"]
        new_time = self.current_time if self.current_time is not None else 0.0

        try:
            old_time_float = float(old_time)
            new_time_float = float(new_time)
        except (ValueError, TypeError):
            # Если не можем преобразовать, просто даём добро
            return True

        reply = QMessageBox.question(
            self,
            "Перезапись результата",
            (
                f'Машинка "{car_name}" уже есть в таблице результатов.\n\n'
                f"Старое время: {old_time_float:.3f}\n"
                f"Новое время: {new_time_float:.3f}\n\n"
                f"Перезаписать результат?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    # ===== СОХРАНЕНИЕ РЕЗУЛЬТАТА =====
    def save_time(self):
        if self.current_time is None:
            self.log("Нет времени для сохранения")
            return

        car_name = self.resolve_car_name()

        if not self.confirm_overwrite_existing_car(car_name):
            self.log(f'Сохранение отменено. Машинка "{car_name}" не была обновлена')
            return

        try:
            # Гарантируем, что time - это float
            time_to_save = float(self.current_time)
            self.log(f'Сохранение результата. Машинка: {car_name}, время: {time_to_save:.3f}')
        except (ValueError, TypeError) as e:
            self.log(f"Ошибка: Невозможно преобразовать время в float: {self.current_time} ({e})")
            return

        # Пока сохраняем результат только в таблицу программы.
        # Массовая отправка в Google Sheets будет выполняться отдельной кнопкой.
        sheets_status = "PENDING"
        self.sheets_label.setText("Google Sheets: готово к выгрузке")
        self.log("Результат сохранён в таблицу программы и ожидает общей выгрузки в Google Sheets")

        self.results_manager.upsert_result(car_name, time_to_save, sheets_status, self.car_db.get_car_extra_data(car_name))
        self.save_btn.setEnabled(False)

    # ===== ОЧИСТКА ТАБЛИЦЫ =====
    def clear_results_table(self):
        if not self.results_manager.results_data:
            self.log("Таблица результатов уже пустая")
            return

        reply = QMessageBox.question(
            self,
            "Очистка таблицы",
            "Очистить всю таблицу результатов в программе?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            self.log("Очистка таблицы отменена")
            return

        self.results_manager.clear_results()
        self.log("Таблица результатов очищена")

    # ===== СБРОС ЗАЕЗДА =====
    def reset_race(self):
        self.network_manager.send_command_to_esp32("RESET")

        self.live_timer.stop()
        self.race_start_time = None
        self.current_time = None
        self.finish_time_from_module = None

        self.mode_label.setText("Режим системы: READY")
        self.time_label.setText("Время: 0.000")
        self.time_display.setText("0.000")
        self.set_ready_style()

        self.start_beam.setText("Стартовый луч: Locked")
        self.finish_beam.setText("Финишный луч: Locked")
        self.save_btn.setEnabled(False)
        self.update_google_status_label()

        self.log("Система сброшена и готова к новому заезду")

    # ===== ОБРАБОТКА СООБЩЕНИЙ ОТ ESP32 =====
    def handle_esp32_message(self, message):
        if message == "CONNECTED":
            self.finish_connection_state_signal.emit(True)
            return

        if message == "CONNECTED_START":
            self.start_connection_state_signal.emit(True)
            return

        if message == "START":
            self.mode_label.setText("Режим системы: RACE")
            self.start_beam.setText("Стартовый луч: Free")
            self.time_label.setText("Время: 0.000")
            self.time_display.setText("0.000")
            self.current_time = None
            self.save_btn.setEnabled(False)

            self.race_start_time = time.time()
            self.set_race_style()
            self.live_timer.start(10)
            return

        if message == "FINISH":
            self.mode_label.setText("Режим системы: FINISH")
            self.finish_beam.setText("Финишный луч: Triggered")
            self.live_timer.stop()
            self.set_finish_style()
            self.flash_finish()
            return

        if message == "READY":
            self.live_timer.stop()
            self.race_start_time = None
            self.current_time = None
            self.mode_label.setText("Режим системы: READY")
            self.time_label.setText("Время: 0.000")
            self.time_display.setText("0.000")
            self.set_ready_style()
            self.start_beam.setText("Стартовый луч: Locked")
            self.finish_beam.setText("Финишный луч: Locked")
            self.save_btn.setEnabled(False)
            self.update_google_status_label()
            return

        if message.startswith("TEMP_START:"):
            temp_value = message.replace("TEMP_START:", "").strip()
            self.start_temp_label.setText(f"{temp_value} °C")
            return

        if message.startswith("TEMP_FINISH:"):
            temp_value = message.replace("TEMP_FINISH:", "").strip()
            self.finish_temp_label.setText(f"{temp_value} °C")
            return

        if message.startswith("TIME:"):
            time_value = message.replace("TIME:", "").strip()
            self.time_label.setText(f"Время: {time_value}")
            self.time_display.setText(time_value)

            try:
                time_float = float(time_value)
                # Приоритет: используем время от FINISH модуля если получили его
                # Иначе используем время от ПК
                if self.race_start_time is not None:
                    # Мы в режиме гонки
                    self.finish_time_from_module = time_float
                    self.current_time = time_float
                    self.log(f"Получено точное время от платы: {time_float:.3f}s")
                else:
                    # Может быть, это время от датчика температуры
                    pass
                    
                self.save_btn.setEnabled(True)
                self.update_google_status_label()
            except ValueError:
                self.log(f"Ошибка парсинга времени: '{time_value}'")
                self.current_time = None
                self.save_btn.setEnabled(False)
                self.update_google_status_label()
            return

    # ===== УДАЛЕНИЕ ЗАПИСИ =====
    def delete_race(self):
        selected_row = self.history.currentRow()

        if selected_row < 0:
            self.log("Не выбрана запись для удаления")
            return

        car_item = self.history.item(selected_row, 1)
        if car_item is None:
            self.log("Не удалось определить машинку для удаления")
            return

        car_name = car_item.text().strip()

        reply = QMessageBox.question(
            self,
            "Удаление записи",
            f'Удалить запись машинки "{car_name}" из таблицы результатов?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            self.log("Удаление отменено")
            return

        existing_index = self.results_manager.find_result_index_by_car(car_name)
        if existing_index >= 0:
            self.results_manager.delete_result(car_name)
            self.log(f'Запись машинки "{car_name}" удалена')
        else:
            self.log("Запись не найдена во внутренней таблице")

    # ===== GOOGLE SHEETS: ОТПРАВИТЬ ВСЕ РЕЗУЛЬТАТЫ =====
    def export_all_results(self):
        if not self.results_manager.results_data:
            self.log("Нет результатов для отправки в Google Sheets")
            self.sheets_label.setText("Google Sheets: нет данных")
            return

        self.log("Запущена отправка всех результатов в Google Sheets")
        self.sheets_label.setText("Google Sheets: отправка...")

        success = self.google_sheets.send_all_results_to_sheets(self.results_manager.results_data)

        if success:
            for row in self.results_manager.results_data:
                row["sheets"] = "OK"

            self.results_manager.refresh_results_table()
            self.results_manager.save_to_file()  # Автосохранение статуса отправки
            self.sheets_label.setText("Google Sheets: отправлено")
            self.log("Все результаты успешно отправлены в Google Sheets")
        else:
            for row in self.results_manager.results_data:
                row["sheets"] = "FAIL"

            self.results_manager.refresh_results_table()
            self.results_manager.save_to_file()  # Автосохранение статуса отправки
            self.sheets_label.setText("Google Sheets: ошибка")
            self.log("Ошибка массовой отправки результатов в Google Sheets")

    # ===== ОКНО: О ПРОГРАММЕ =====
    def show_about(self):
        about_text = f"""
Hot Wheels Timer

v{APP_VERSION_LABEL}

Функции:
• управление стартом и финишем ESP32
• измерение времени заезда
• таблица результатов с сортировкой
• расчет отставания (Gap)
• подсветка Top-3
• база машинок из файла cars.json
• интеграция с Google Sheets

Автор: Zeberdee
"""
        QMessageBox.information(self, "О программе", about_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TimerApp()
    window.show()
    sys.exit(app.exec())
