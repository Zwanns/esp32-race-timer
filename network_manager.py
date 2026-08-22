import math
import socket
import threading
import time


MODULE_OFFLINE_TIMEOUT_SEC = 15.0
SOCKET_CONNECT_TIMEOUT_SEC = 5.0
SOCKET_READ_POLL_SEC = 1.0
RECONNECT_DELAY_SEC = 2.0


class ModuleTimeoutError(ConnectionError):
    """Raised when a connected module stops sending valid protocol messages."""


class ModuleHealth:
    """Thread-safe application-level connection health for one ESP32 module."""

    def __init__(self, timeout_sec=MODULE_OFFLINE_TIMEOUT_SEC):
        self.timeout_sec = timeout_sec
        self.connected_at = None
        self.last_message_time = None
        self.online = False
        self.ever_online = False
        self._lock = threading.Lock()

    def mark_socket_connected(self, now=None):
        with self._lock:
            self.connected_at = time.monotonic() if now is None else now
            self.last_message_time = None

    def mark_valid_message(self, now=None):
        with self._lock:
            self.last_message_time = time.monotonic() if now is None else now
            became_online = not self.online
            was_previously_online = self.ever_online
            self.online = True
            self.ever_online = True
            return became_online, was_previously_online

    def mark_disconnected(self):
        with self._lock:
            was_online = self.online
            self.online = False
            self.connected_at = None
            self.last_message_time = None
            return was_online

    def last_message(self):
        with self._lock:
            return self.last_message_time

    def message_age(self, now=None):
        with self._lock:
            reference_time = self.last_message_time
            if reference_time is None:
                reference_time = self.connected_at
            if reference_time is None:
                return None
            current_time = time.monotonic() if now is None else now
            return max(0.0, current_time - reference_time)

    def has_timed_out(self, now=None):
        age = self.message_age(now)
        return age is not None and age > self.timeout_sec


class NetworkManager:
    def __init__(
        self,
        finish_ip="192.168.0.210",
        finish_port=5000,
        start_ip="192.168.0.193",
        start_port=5001,
        offline_timeout_sec=MODULE_OFFLINE_TIMEOUT_SEC,
    ):
        self.finish_ip = finish_ip
        self.finish_port = finish_port
        self.start_ip = start_ip
        self.start_port = start_port

        self.finish_sock = None
        self.start_sock = None
        self._socket_lock = threading.Lock()

        self._health = {
            "FINISH": ModuleHealth(offline_timeout_sec),
            "START": ModuleHealth(offline_timeout_sec),
        }

        self.finish_connection_state_signal = None
        self.start_connection_state_signal = None
        self.esp32_message_signal = None
        self.log_signal = None

    @property
    def last_start_message_time(self):
        return self._health["START"].last_message()

    @property
    def last_finish_message_time(self):
        return self._health["FINISH"].last_message()

    def set_signals(self, finish_connection_signal, start_connection_signal, esp32_message_signal, log_signal):
        self.finish_connection_state_signal = finish_connection_signal
        self.start_connection_state_signal = start_connection_signal
        self.esp32_message_signal = esp32_message_signal
        self.log_signal = log_signal

    def start_network(self):
        self._start_module_thread("FINISH", self.finish_ip, self.finish_port)

    def start_start_network(self):
        self._start_module_thread("START", self.start_ip, self.start_port)

    def _start_module_thread(self, module, ip_address, port):
        thread = threading.Thread(
            target=self._network_loop,
            args=(module, ip_address, port),
            daemon=True,
            name=f"{module.lower()}-esp32-network",
        )
        thread.start()

    def _network_loop(self, module, ip_address, port):
        health = self._health[module]

        while True:
            sock = None
            try:
                action = "reconnecting" if health.ever_online else "connecting"
                self._log(f"{module} {action}...")

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._configure_keepalive(sock)
                sock.settimeout(SOCKET_CONNECT_TIMEOUT_SEC)
                sock.connect((ip_address, port))
                sock.settimeout(SOCKET_READ_POLL_SEC)
                self._set_socket(module, sock)
                health.mark_socket_connected()
                self._log(f"{module} TCP connected; awaiting valid message")

                receive_buffer = b""
                while True:
                    try:
                        data = sock.recv(1024)
                    except socket.timeout:
                        if health.has_timed_out():
                            age = health.message_age()
                            raise ModuleTimeoutError(
                                f"{module} timeout after {age:.1f} s"
                            )
                        continue

                    if data == b"":
                        raise ConnectionError(f"{module} peer closed the connection")

                    receive_buffer += data
                    while b"\n" in receive_buffer:
                        raw_line, receive_buffer = receive_buffer.split(b"\n", 1)
                        line = raw_line.decode("utf-8").strip()
                        if not line:
                            continue
                        self._handle_line(module, line)

                    if len(receive_buffer) > 8192:
                        raise ValueError(f"{module} message exceeds receive buffer limit")

                    if health.has_timed_out():
                        age = health.message_age()
                        raise ModuleTimeoutError(
                            f"{module} timeout after {age:.1f} s"
                        )

            except ModuleTimeoutError as error:
                self._log(str(error))
            except (
                ConnectionResetError,
                ConnectionAbortedError,
                BrokenPipeError,
                ConnectionError,
                UnicodeDecodeError,
                ValueError,
                OSError,
            ) as error:
                self._log(f"{module} connection lost: {error}")
            finally:
                self._clear_socket(module, sock)
                if sock is not None:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    try:
                        sock.close()
                    except OSError:
                        pass

                if health.mark_disconnected():
                    self._connection_signal(module).emit(False)
                    self._log(f"{module} marked offline")

            time.sleep(RECONNECT_DELAY_SEC)

    def _handle_line(self, module, line):
        if not self.is_valid_message(module, line):
            self._log(f"{module} ignored invalid message: {line}")
            return

        became_online, was_previously_online = self._health[module].mark_valid_message()
        if became_online:
            self._connection_signal(module).emit(True)
            status = "reconnected" if was_previously_online else "connected"
            self._log(f"{module} {status}")

        if not line.startswith("TEMP_"):
            self._log(f"{module} ESP32: {line}")
        self.esp32_message_signal.emit(line)

    @staticmethod
    def is_valid_message(module, line):
        if module == "START":
            if line in {"CONNECTED_START", "START"}:
                return True
            return NetworkManager._has_finite_number(line, "TEMP_START:")

        if module == "FINISH":
            if line in {"CONNECTED", "START", "FINISH", "READY", "RESULT_READY"}:
                return True
            return (
                NetworkManager._has_finite_number(line, "TEMP_FINISH:")
                or NetworkManager._has_finite_number(line, "TIME:")
            )

        return False

    @staticmethod
    def _has_finite_number(line, prefix):
        if not line.startswith(prefix):
            return False
        try:
            return math.isfinite(float(line[len(prefix):].strip()))
        except ValueError:
            return False

    def _configure_keepalive(self, sock):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        except OSError as error:
            self._log(f"TCP keepalive setup skipped: {error}")

    def _connection_signal(self, module):
        if module == "START":
            return self.start_connection_state_signal
        return self.finish_connection_state_signal

    def _set_socket(self, module, sock):
        with self._socket_lock:
            if module == "START":
                self.start_sock = sock
            else:
                self.finish_sock = sock

    def _clear_socket(self, module, expected_sock):
        with self._socket_lock:
            attribute = "start_sock" if module == "START" else "finish_sock"
            if getattr(self, attribute) is expected_sock:
                setattr(self, attribute, None)

    def _log(self, message):
        if self.log_signal is not None:
            self.log_signal.emit(message)

    def send_command_to_esp32(self, command):
        with self._socket_lock:
            sock = self.finish_sock

        if sock is None:
            self._log("Нет подключения к FINISH ESP32")
            return

        try:
            sock.sendall((command + "\n").encode("utf-8"))
            self._log("Команда отправлена: " + command)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as error:
            self._log("Ошибка отправки команды: " + str(error))
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
