#pragma once

#include <Arduino.h>
#include <esp_wifi.h>
#include <esp32-hal-bt.h>
#if CONFIG_BT_ENABLED
#include <esp_bt.h>
#endif

// Local controls only. Never initialize either radio just to turn it off.
namespace RadioPower {
inline bool wifiOff() {
  wifi_mode_t mode=WIFI_MODE_NULL;
  // Require the driver to be deinitialized, rather than merely disconnected.
  return esp_wifi_get_mode(&mode)==ESP_ERR_WIFI_NOT_INIT;
}

inline bool bluetoothOff() {
#if CONFIG_BT_ENABLED
  return esp_bt_controller_get_status()==ESP_BT_CONTROLLER_STATUS_IDLE;
#else
  return true;
#endif
}

inline bool disable() {
  const esp_err_t stopped=esp_wifi_stop();
  const esp_err_t deinitialized=esp_wifi_deinit();
#if CONFIG_BT_ENABLED
  const bool btOk=btStop(); // Already IDLE is success; never calls btStart().
#else
  const bool btOk=true;
#endif
  // An untouched driver is the normal boot state, not an error.
  const bool wifiOk=(stopped==ESP_OK||stopped==ESP_ERR_WIFI_NOT_INIT)
    &&(deinitialized==ESP_OK||deinitialized==ESP_ERR_WIFI_NOT_INIT);
  return wifiOk&&btOk&&wifiOff()&&bluetoothOff();
}
}
