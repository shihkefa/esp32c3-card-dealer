#pragma once
#include <stdint.h>
#include "EdgeEvent.h"

#if defined(ARDUINO_ARCH_ESP32) || defined(ESP_PLATFORM)
#include <esp_attr.h>
#define EXIT_QUALIFIER_IRAM_ATTR IRAM_ATTR
#else
#define EXIT_QUALIFIER_IRAM_ATTR
#endif

// CHANGE interrupts observe every raw transition; the periodic timer calls poll.
// Only the resulting qualified transitions belong in the consumer event queue.
// Keeping raw observations is important: fixed-period GPIO sampling alone can
// alias narrow motor-PWM glitches into an apparently continuous blocked level.
//
// The caller owns synchronization. Both ISR paths and reset must hold the same
// lock, with timestamps captured inside that lock so calls remain chronological
// (modulo micros() wrap). Instances and output events used by ISRs must be in
// internal RAM. These methods only use scalar arithmetic and memory accesses.
class ExitQualifier {
 public:
  static constexpr uint32_t kBlockedUs = 1500;
  // A partly lifted or fluttering card can briefly uncover the beam. Wait for
  // continuous light before publishing a trailing edge and counting a card.
  static constexpr uint32_t kClearUs = 12000;

  // Match the controller's initial raw state. A blocked input at boot is not a
  // newly arriving card, and reset therefore emits no event.
  void EXIT_QUALIFIER_IRAM_ATTR reset(bool blocked, uint32_t us) {
    candidate_ = qualified_ = blocked;
    changedUs_ = us;
  }

  bool EXIT_QUALIFIER_IRAM_ATTR observe(bool blocked, uint32_t us, ExitEdge& event) {
    // Settle the old candidate first. In particular, a high pulse ending at
    // exactly 1500 us remains valid even if no timer tick occurred at its end.
    const bool ready = poll(us, event);
    if (blocked != candidate_) {
      candidate_ = blocked;
      changedUs_ = us;
    }
    return ready;
  }

  bool EXIT_QUALIFIER_IRAM_ATTR poll(uint32_t us, ExitEdge& event) {
    if (candidate_ == qualified_) return false;
    const uint32_t required = candidate_ ? kBlockedUs : kClearUs;
    if (uint32_t(us - changedUs_) < required) return false;
    qualified_ = candidate_;
    // Preserve the original candidate time for DealerCore's existing edge
    // qualification and queued whole-pulse handling, rather than the poll time.
    event.us = changedUs_;
    event.blocked = qualified_;
    return true;
  }

 private:
  bool candidate_ = false;
  bool qualified_ = false;
  uint32_t changedUs_ = 0;
};

#undef EXIT_QUALIFIER_IRAM_ATTR
