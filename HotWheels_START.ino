#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <WiFiClient.h>

#define LED_GREEN 26
#define LED_RED 25
#define BUTTON_PIN 0
#define SENSOR_PIN 27  // новый ИК-датчик на старте (b20)

const char* WIFI_SSID = "UPC2859211";
const char* WIFI_PASS = "k6ppCtxQgxmn";

uint8_t finishMac[] = {0xA4, 0xF0, 0x0F, 0x64, 0x22, 0xF0};

WiFiServer tcpServer(5001);
WiFiClient pcClient;

typedef struct {
  char msg[16];
} Payload;

bool raceRunning = false;
bool buttonWasReleased = true;

// Датчик стартовой линии
bool startSensorWasBlocked = false;
unsigned long startSensorBlockedTime = 0;
const unsigned long START_SENSOR_DEBOUNCE_MS = 30; // антидребезг

unsigned long lastTempSendTime = 0;

void setReadyState() {
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_RED, LOW);
}

void setRunningState() {
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, HIGH);
}

void sendToPc(String message) {
  if (pcClient && pcClient.connected()) {
    pcClient.println(message);
    Serial.print("Sent to PC: ");
    Serial.println(message);
  }
}

void connectWiFiForChannel() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("Connecting START to Wi-Fi");
  int tries = 0;

  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("START Wi-Fi connected, IP: ");
    Serial.println(WiFi.localIP());

    uint8_t ch = WiFi.channel();
    Serial.print("START Wi-Fi channel: ");
    Serial.println(ch);
  } else {
    Serial.println("START Wi-Fi connection failed");
  }
}

void onSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  Serial.print("Send status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "OK" : "FAIL");
}

void onReceive(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  Payload data;
  memcpy(&data, incomingData, sizeof(data));

  Serial.print("Received: ");
  Serial.println(data.msg);

  if (strcmp(data.msg, "RESET") == 0) {
    raceRunning = false;
    startSensorWasBlocked = false;
    setReadyState();
    Serial.println("Start module reset to READY");
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(SENSOR_PIN, INPUT); // b20 -> GPIO27; HIGH / LOW от ИК-датчика

  // Тест светодиодов при запуске
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_RED, HIGH);
  delay(2000);

  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  delay(500);

  setReadyState();

  connectWiFiForChannel();

  tcpServer.begin();
  Serial.println("START TCP server started on port 5001");

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }

  esp_now_register_send_cb(onSent);
  esp_now_register_recv_cb(onReceive);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, finishMac, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }

  Serial.println("Start module ready");
  Serial.println("BOOT = START");
}

void loop() {
  if (!pcClient || !pcClient.connected()) {
    pcClient = tcpServer.available();
    if (pcClient) {
      Serial.println("PC connected to START TCP server");
      sendToPc("CONNECTED_START");
    }
  }

  if (millis() - lastTempSendTime >= 5000) {
    float tempC = temperatureRead();
    String tempMsg = "TEMP_START:";
    tempMsg += String(tempC, 1);
    sendToPc(tempMsg);
    lastTempSendTime = millis();
  }

  // Новый ИК-датчик стартовой линии
  bool sensorBlocked = (digitalRead(SENSOR_PIN) == LOW); // LOW = перекрыт, HIGH = свободен
  if (!raceRunning) {
    if (sensorBlocked && !startSensorWasBlocked) {
      // зафиксировали автомобиль на старте
      startSensorWasBlocked = true;
      startSensorBlockedTime = millis();
      Serial.println("Start sensor: car detected");
      setReadyState();
    }

    if (startSensorWasBlocked && !sensorBlocked) {
      // автомобиль вышел, запускаем гонку
      if (millis() - startSensorBlockedTime >= START_SENSOR_DEBOUNCE_MS) {
        Serial.println("Start sensor: car left, race START");
        Payload data;
        strcpy(data.msg, "START");

        setRunningState();
        raceRunning = true;
        sendToPc("START");
        esp_now_send(finishMac, (uint8_t *)&data, sizeof(data));

        startSensorWasBlocked = false;
        buttonWasReleased = false;
      }
    }
  }

  bool buttonPressed = (digitalRead(BUTTON_PIN) == LOW);

  if (!raceRunning && buttonPressed && buttonWasReleased) {
    Payload data;
    strcpy(data.msg, "START");

    Serial.println("START triggered");

    setRunningState();
    raceRunning = true;

    // Отправляем START в программу на ПК
    sendToPc("START");

    // Отправляем START на финишный модуль
    esp_now_send(finishMac, (uint8_t *)&data, sizeof(data));

    buttonWasReleased = false;
  }

  if (!buttonPressed) {
    buttonWasReleased = true;
  }
}