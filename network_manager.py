import socket
import threading
import time

class NetworkManager:
    def __init__(self, finish_ip="192.168.0.210", finish_port=5000, start_ip="192.168.0.193", start_port=5001):
        self.finish_ip = finish_ip
        self.finish_port = finish_port
        self.start_ip = start_ip
        self.start_port = start_port

        self.finish_sock = None
        self.start_sock = None

        self.finish_connection_state_signal = None
        self.start_connection_state_signal = None
        self.esp32_message_signal = None
        self.log_signal = None

    def set_signals(self, finish_connection_signal, start_connection_signal, esp32_message_signal, log_signal):
        self.finish_connection_state_signal = finish_connection_signal
        self.start_connection_state_signal = start_connection_signal
        self.esp32_message_signal = esp32_message_signal
        self.log_signal = log_signal

    def start_network(self):
        def network_thread():
            while True:
                try:
                    self.log_signal.emit("Попытка подключения к FINISH ESP32...")
                    self.finish_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.finish_sock.settimeout(5)
                    self.finish_sock.connect((self.finish_ip, self.finish_port))
                    self.finish_sock.settimeout(None)

                    self.log_signal.emit("Подключено к FINISH ESP32")
                    self.finish_connection_state_signal.emit(True)

                    while True:
                        data = self.finish_sock.recv(1024)

                        if not data:
                            raise ConnectionError("FINISH соединение закрыто")

                        message = data.decode().strip()
                        if not message:
                            continue

                        for line in message.splitlines():
                            line = line.strip()
                            if not line:
                                continue

                            if not line.startswith("TEMP_"):
                                self.log_signal.emit("FINISH ESP32: " + line)

                            self.esp32_message_signal.emit(line)

                except Exception as e:
                    self.finish_sock = None
                    self.log_signal.emit("Связь с FINISH ESP32 потеряна: " + str(e))
                    self.finish_connection_state_signal.emit(False)

                finally:
                    try:
                        if self.finish_sock:
                            self.finish_sock.close()
                    except Exception:
                        pass
                    self.finish_sock = None

                time.sleep(2)

        thread = threading.Thread(target=network_thread, daemon=True)
        thread.start()

    def start_start_network(self):
        def network_thread():
            while True:
                try:
                    self.log_signal.emit("Попытка подключения к START ESP32...")
                    self.start_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.start_sock.settimeout(5)
                    self.start_sock.connect((self.start_ip, self.start_port))
                    self.start_sock.settimeout(None)

                    self.log_signal.emit("Подключено к START ESP32")
                    self.start_connection_state_signal.emit(True)

                    while True:
                        data = self.start_sock.recv(1024)

                        if not data:
                            raise ConnectionError("START соединение закрыто")

                        message = data.decode().strip()
                        if not message:
                            continue

                        for line in message.splitlines():
                            line = line.strip()
                            if not line:
                                continue

                            if not line.startswith("TEMP_"):
                                self.log_signal.emit("START ESP32: " + line)

                            self.esp32_message_signal.emit(line)

                except Exception as e:
                    self.start_sock = None
                    self.log_signal.emit("Связь со START ESP32 потеряна: " + str(e))
                    self.start_connection_state_signal.emit(False)

                finally:
                    try:
                        if self.start_sock:
                            self.start_sock.close()
                    except Exception:
                        pass
                    self.start_sock = None

                time.sleep(2)

        thread = threading.Thread(target=network_thread, daemon=True)
        thread.start()

    def send_command_to_esp32(self, command):
        try:
            if self.finish_sock:
                self.finish_sock.sendall((command + "\n").encode())
                self.log_signal.emit("Команда отправлена: " + command)
            else:
                self.log_signal.emit("Нет подключения к FINISH ESP32")
        except Exception as e:
            self.log_signal.emit("Ошибка отправки команды: " + str(e))