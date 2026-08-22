#include <WiFi.h>
#include <esp_now.h>
#include <WiFiClient.h>

#define FINISH_BUTTON 0
#define FINISH_SENSOR_PIN 27  // новый ИК-датчик на финише
#define LED_GREEN 26
#define LED_RED 25

const char* WIFI_SSID = "UPC2859211";
const char* WIFI_PASS = "k6ppCtxQgxmn";

// MAC стартовой платы: B0:CB:D8:C8:09:94
uint8_t startMac[] = {0xB0, 0xCB, 0xD8, 0xC8, 0x09, 0x94};

WiFiServer tcpServer(5000);
WiFiClient pcClient;

typedef struct {
  char msg[16];
} Payload;

unsigned long startTime = 0;
bool raceRunning = false;
bool buttonWasReleased = true;
float lastRaceTime = 0;
unsigned long lastTempSendTime = 0;
unsigned long finishLockUntil = 0;

// Датчик финишной линии
bool finishSensorWasBlocked = false;
unsigned long finishSensorBlockedTime = 0;
const unsigned long FINISH_SENSOR_DEBOUNCE_MS = 30; // антидребезг

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

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("Connecting to Wi-Fi...");
  int tries = 0;

  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Wi-Fi connected, IP: ");
    Serial.println(WiFi.localIP());

    Serial.print("FINISH Wi-Fi channel: ");
    Serial.println(WiFi.channel());
  } else {
    Serial.println("Wi-Fi connection failed");
  }
}

void sendResetToStart() {
  Payload data;
  strcpy(data.msg, "RESET");

  esp_err_t result = esp_now_send(startMac, (uint8_t *)&data, sizeof(data));

  Serial.print("RESET send result: ");
  Serial.println(result == ESP_OK ? "ESP_OK" : "ERR");
}

void onReceive(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  Payload data;
  memcpy(&data, incomingData, sizeof(data));

  Serial.print("Received: ");
  Serial.println(data.msg);

  if (strcmp(data.msg, "START") == 0) {
    Serial.println("START received");
    sendToPc("START");
    startTime = millis();
    raceRunning = true;
    setRunningState();
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(FINISH_BUTTON, INPUT_PULLUP);
  pinMode(FINISH_SENSOR_PIN, INPUT); // HIGH / LOW от ИК-датчика
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);

  // Тест светофора при включении платы
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_RED, HIGH);
  delay(2000);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  delay(500);
  setReadyState();

  connectWiFi();

  tcpServer.begin();
  Serial.println("TCP server started on port 5000");

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }

  esp_now_register_recv_cb(onReceive);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, startMac, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add START peer");
    return;
  }

  Serial.println("Finish module ready");
  Serial.println("Waiting for START...");
}

void loop() {
  if (!pcClient || !pcClient.connected()) {
    pcClient = tcpServer.available();
    if (pcClient) {
      Serial.println("PC connected to TCP server");
      sendToPc("CONNECTED");
    }
  }

  if (pcClient && pcClient.connected() && pcClient.available()) {
    String command = pcClient.readStringUntil('\n');
    command.trim();

    Serial.print("Command from PC: ");
    Serial.println(command);

    if (command == "RESET") {
      sendResetToStart();
      raceRunning = false;
      startTime = 0;
      lastRaceTime = 0;
      finishSensorWasBlocked = false;
      setReadyState();
      sendToPc("READY");
      Serial.println("System reset by PC command");
    }
  }

  bool buttonPressed = (digitalRead(FINISH_BUTTON) == LOW);

  if (millis() - lastTempSendTime >= 5000) {
    float tempC = temperatureRead();
    String tempMsg = "TEMP_FINISH:";
    tempMsg += String(tempC, 1);
    sendToPc(tempMsg);
    lastTempSendTime = millis();
  }

  // Новый ИК-датчик финишной линии
  bool sensorBlocked = (digitalRead(FINISH_SENSOR_PIN) == LOW); // LOW = перекрыт, HIGH = свободен
  if (raceRunning) {
    if (sensorBlocked && !finishSensorWasBlocked) {
      // зафиксировали автомобиль на финише
      finishSensorWasBlocked = true;
      finishSensorBlockedTime = millis();
      Serial.println("Finish sensor: car detected");
    }

    if (finishSensorWasBlocked && !sensorBlocked) {
      // автомобиль прошел, фиксируем финиш
      if (millis() - finishSensorBlockedTime >= FINISH_SENSOR_DEBOUNCE_MS && millis() >= finishLockUntil) {
        Serial.println("Finish sensor: car passed, race FINISH");
        unsigned long finishTime = millis();
        unsigned long raceTimeMs = finishTime - startTime;
        float raceTimeSec = raceTimeMs / 1000.0;

        finishLockUntil = millis() + 2000;  // блокировка повторного финиша

        Serial.print("FINISH! Time (ms): ");
        Serial.println(raceTimeMs);
        Serial.print("Time (s): ");
        Serial.println(raceTimeSec, 3);

        sendToPc("FINISH");
        String msg = "TIME:";
        msg += String(raceTimeSec, 3);
        sendToPc(msg);
        lastRaceTime = raceTimeSec;
        sendToPc("RESULT_READY");

        raceRunning = false;
        finishSensorWasBlocked = false;
        setReadyState();
        Serial.println("Race result ready by sensor");
      }
    }
  }

  if (raceRunning && buttonPressed && buttonWasReleased && millis() >= finishLockUntil) {
    unsigned long finishTime = millis();
    unsigned long raceTimeMs = finishTime - startTime;
    float raceTimeSec = raceTimeMs / 1000.0;
    
    finishLockUntil = millis() + 2000;

    sendToPc("FINISH");

    Serial.print("FINISH! Time (ms): ");
    Serial.println(raceTimeMs);

    Serial.print("Time (s): ");
    Serial.println(raceTimeSec, 3);

    String msg = "TIME:";
    msg += String(raceTimeSec, 3);
    sendToPc(msg);

    lastRaceTime = raceTimeSec;
    sendToPc("RESULT_READY");
    Serial.println("Race result ready");

    raceRunning = false;
    setReadyState();
    buttonWasReleased = false;

    delay(1000);
    Serial.println("Waiting for START...");
  }

  if (!buttonPressed) {
    buttonWasReleased = true;
  }
}
