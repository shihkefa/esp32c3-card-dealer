#pragma once
#include <stdint.h>

namespace dealer {
// Software experiment limits, not verified ratings for a loaded 28BYJ-48.
// The scheduler still emits at most one half-step per 100us tick.
constexpr uint16_t kDefaultYawRate=600;
constexpr uint16_t kDefaultYawAcceleration=300;
constexpr uint16_t kMaxYawRate=10000;  // One commanded half-step per 100 us timer interrupt.
constexpr uint16_t kYawRatePerPercent=kMaxYawRate/100;
constexpr uint16_t kMinYawRate=kYawRatePerPercent;
// For an old fractional percentage the first button press moves in the
// requested direction to the nearest whole percentage.
inline uint16_t nextYawRate(uint16_t current,int direction) {
  if (direction>0 && current<kMaxYawRate) return uint16_t((current/kYawRatePerPercent+1)*kYawRatePerPercent);
  if (direction<0 && current>kMinYawRate) return uint16_t((current-1)/kYawRatePerPercent*kYawRatePerPercent);
  return current;
}
constexpr uint16_t kMaxYawAcceleration=24000;
constexpr uint16_t kFastHomePollRate=3600;

inline uint32_t positioningPollMs(uint16_t rate,uint32_t idlePollMs) {
  if (rate>=kFastHomePollRate) return 1;
  return rate>1200 ? 2 : idlePollMs;
}
}
