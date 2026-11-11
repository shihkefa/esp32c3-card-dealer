#pragma once
#include <stdint.h>

// ESP32-C3 SuperMini with native USB. Keep GPIO18/19 for USB and avoid
// strapping GPIO2/8/9. UART0 is NOT used: GPIO21/20 carry I2C instead.
namespace Board {
constexpr uint8_t kStepperPins[4] = {0, 1, 3, 4}; // ULN2003 IN1..IN4
constexpr uint8_t kFeedIn1 = 5;   // DRV8833 AIN1
constexpr uint8_t kFeedIn2 = 6;   // DRV8833 AIN2
constexpr uint8_t kEjectIn1 = 7;  // DRV8833 BIN1; BIN2 permanently GND
constexpr uint8_t kExitPin = 10;  // bare ITR9608-F collector, 10k to 3V3
constexpr uint8_t kSda = 21;
constexpr uint8_t kScl = 20;
constexpr uint8_t kPcfAddress = 0x20;  // PCF8574T, A0/A1/A2 = GND
constexpr uint8_t kOledAddress = 0x3C; // SSD1306, 128x64 only
constexpr uint8_t kHomePcfBit = 4;    // P0..P3: SET / - / + / RUN
constexpr bool kExitBlockedHigh = true;
constexpr bool kHomeBlockedHigh = true;
constexpr int8_t kYawElectricalDirection = 1; // change to -1 if yaw is CCW
constexpr uint32_t kI2cHz = 100000; // PCF8574 standard-mode limit
constexpr uint16_t kWireTimeoutMs = 8;
constexpr uint32_t kPwmHz = 20000;
constexpr uint32_t kStepperTickUs = 100;
constexpr uint32_t kPcfPollMs = 5;
constexpr uint32_t kDisplayFrameMs = 250;
constexpr bool uniquePins() {
  constexpr uint8_t p[] = {kStepperPins[0],kStepperPins[1],kStepperPins[2],kStepperPins[3],kFeedIn1,kFeedIn2,kEjectIn1,kExitPin,kSda,kScl};
  for (unsigned i=0;i<sizeof(p);++i)
    for (unsigned j=i+1;j<sizeof(p);++j) if (p[i]==p[j]) return false;
  return true;
}
static_assert(uniquePins(), "GPIO assignments must be unique");
static_assert(kYawElectricalDirection==1 || kYawElectricalDirection== -1,"Yaw direction is +1 or -1");
static_assert(kPcfAddress!=kOledAddress,"I2C addresses must not collide");
}
