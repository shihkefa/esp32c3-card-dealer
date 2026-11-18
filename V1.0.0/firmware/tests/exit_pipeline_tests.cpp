#include "DealerCore.h"
#include "ExitQualifier.h"
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>

using namespace dealer;
static unsigned checks = 0;
static unsigned cases = 0;
#define CHECK(condition) do { \
  ++checks; \
  if (!(condition)) { \
    std::fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #condition); \
    std::exit(1); \
  } \
} while (0)

struct PipelineHardware final : Hardware {
  int32_t location = 0;
  int16_t feedValue = 0;
  uint8_t ejectValue = 0;
  bool rawBlocked = false;
  bool holding = false;
  unsigned moves = 0;
  std::vector<int16_t> feedCommands;
  std::vector<uint8_t> ejectCommands;

  bool moveTo(int32_t target, uint16_t, uint16_t) override {
    location = target;
    ++moves;
    return true;
  }
  int32_t position() const override { return location; }
  bool moving() const override { return false; }
  void setCounterclockwise(bool) override {}
  void stopMotion() override {}
  void hold(bool on) override { holding = on; }
  bool outletRawBlocked() const override { return rawBlocked; }
  void feed(int16_t pwm) override { feedValue = pwm; feedCommands.push_back(pwm); }
  void eject(uint8_t pwm) override { ejectValue = pwm; ejectCommands.push_back(pwm); }
};

// The transport is a bounded mailbox, not a copy of the firmware ring buffer.
// Tests feed real raw transitions and periodic polls through ExitQualifier, then
// give the resulting original timestamps to the real Controller. Motor commands
// are observed here; ActualHardware's electrical 2 ms deadtime is a separate test.
struct Pipeline {
  PipelineHardware hw;
  Controller controller;
  ExitQualifier qualifier;
  uint64_t now = 0;
  uint64_t nextPoll = 100;
  std::vector<ExitEdge> queued;
  bool overflow = false;
  unsigned qualifiedEvents = 0;
  unsigned maximumQueued = 0;

  explicit Pipeline(uint8_t startPwm = 255, uint8_t carryPwm = 200, uint16_t startMs = 100) : controller(hw) {
    Settings settings;
    settings.calibrated = true;
    settings.feedPwm = 175;
    settings.ejectStartPwm = startPwm;
    settings.ejectStartMs = startMs;
    settings.ejectPwm = carryPwm;
    settings.reversePwm = 175;
    settings.reverseMs = 50;
    controller.begin(settings, false, false, 0, 0);
    qualifier.reset(false, 0);
  }
  uint32_t us() const { return uint32_t(now); }
  uint32_t ms() const { return uint32_t(now / 1000); }
  void publish(const ExitEdge& edge) {
    ++qualifiedEvents;
    if (queued.size() == 31) overflow = true;
    else queued.push_back(edge);
    if (queued.size() > maximumQueued) maximumQueued = unsigned(queued.size());
  }
  void consume() {
    const bool lostHistory = overflow;
    overflow = false;
    if (!lostHistory) {
      for (const ExitEdge& edge : queued) {
        controller.rawExitEdge(edge.blocked, edge.us, ms());
      }
    }
    queued.clear();
    controller.tick(ms(), us(), false, true, lostHistory);
  }
  void advanceTo(uint64_t target, bool consumeNormally = true) {
    CHECK(target >= now);
    while (nextPoll <= target) {
      now = nextPoll;
      ExitEdge event;
      if (qualifier.poll(us(), event)) publish(event);
      if (consumeNormally && now % 1000 == 0) consume();
      nextPoll += 100;
    }
    now = target;
  }
  void rawAt(bool blocked, uint64_t at, bool consumeNormally = true) {
    advanceTo(at, consumeNormally);
    hw.rawBlocked = blocked;
    ExitEdge event;
    if (qualifier.observe(blocked, us(), event)) publish(event);
  }
  void startSpinUp() {
    advanceTo(30000);
    CHECK(controller.start(ms(), us()));
    advanceTo(31000);
    CHECK(controller.stage() == Stage::SpinUp);
    const Settings& settings = controller.settings();
    CHECK(hw.feedValue == 0 && hw.ejectValue == (settings.ejectStartMs ? settings.ejectStartPwm : settings.ejectPwm));
  }
  void startFeeding() {
    startSpinUp();
    advanceTo(250000);
    CHECK(controller.stage() == Stage::Feeding);
    CHECK(hw.feedValue == 175 && hw.ejectValue == controller.settings().ejectPwm);
    CHECK(controller.done() == 0 && hw.moves == 1);
  }
  unsigned negativeCommands() const {
    unsigned result = 0;
    for (int16_t command : hw.feedCommands) if (command < 0) ++result;
    return result;
  }
  unsigned ejectCommandsAt(uint8_t pwm) const {
    unsigned result = 0;
    for (uint8_t command : hw.ejectCommands) if (command == pwm) ++result;
    return result;
  }
};

static void motorPwmNoiseDoesNotBecomeCards() {
  ++cases;
  Pipeline p;
  p.startFeeding();
  // A 2 us high glitch every 50 us. Each 100 us timer poll lands inside one
  // glitch, making this an alias trap for a polling-only implementation.
  const uint64_t firstCenter = p.now + 100;
  for (uint64_t center = firstCenter; center < firstCenter + 50000; center += 50) {
    p.rawAt(true, center - 1);
    p.rawAt(false, center + 1);
  }
  p.advanceTo(p.now + 5000);
  CHECK(p.qualifiedEvents == 0 && p.maximumQueued == 0);
  CHECK(p.controller.stage() == Stage::Feeding && p.controller.done() == 0);
  CHECK(p.controller.error() == Error::None);
  CHECK(p.negativeCommands() == 0 && p.hw.feedValue == 175);
  CHECK(p.hw.ejectValue == 200 && p.ejectCommandsAt(200) == 1);
  // No valid card arrives: E04 must stop both outputs.
  p.advanceTo(p.now + 1300000);
  CHECK(p.controller.error() == Error::NoCard && p.controller.done() == 0);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 0);
  CHECK(p.ejectCommandsAt(200) == 1);
}

static void timedEjectionKeepsSpeedThroughSensorEdgesAndRestartsAfterPause() {
  ++cases;
  Pipeline p(245, 155, 65);
  p.startFeeding();
  CHECK(p.hw.ejectValue == 155 && p.ejectCommandsAt(155) == 1);

  const uint64_t noiseAt = p.now + 50;
  p.rawAt(true, noiseAt);
  p.rawAt(false, noiseAt + 1499);
  p.advanceTo(noiseAt + 6000);
  CHECK(p.qualifiedEvents == 0 && p.controller.done() == 0);
  CHECK(p.hw.ejectValue == 155 && p.negativeCommands() == 0);
  CHECK(p.ejectCommandsAt(155) == 1);

  const uint64_t highAt = p.now + 50;
  p.rawAt(true, highAt);
  p.advanceTo(highAt + 1499);
  CHECK(p.controller.stage() == Stage::Feeding);
  CHECK(p.hw.ejectValue == 155 && p.hw.feedValue == 175);
  CHECK(p.ejectCommandsAt(155) == 1);
  p.advanceTo(highAt + 3000);
  CHECK(p.controller.stage() == Stage::Exiting && p.controller.done() == 0);
  CHECK(p.hw.ejectValue == 155 && p.hw.feedValue == -175);
  CHECK(p.ejectCommandsAt(155) == 1 && p.negativeCommands() == 1);

  p.controller.requestPause();
  p.rawAt(false, highAt + 10000);
  p.advanceTo(highAt + 24000);
  CHECK(p.controller.stage() == Stage::Tail && p.controller.done() == 1);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 155);
  CHECK(p.ejectCommandsAt(155) == 1);
  p.advanceTo(highAt + 90000);
  CHECK(p.controller.stage() == Stage::Paused && p.controller.done() == 1);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 0);
  CHECK(p.controller.resume(p.ms(), p.us()));
  p.advanceTo(p.now + 1000);
  const uint64_t restartAt = p.now;
  CHECK(p.controller.stage() == Stage::SpinUp && p.hw.ejectValue == 245);
  CHECK(p.hw.feedValue == 0 && p.ejectCommandsAt(155) == 1);
  p.advanceTo(restartAt + 64000);
  CHECK(p.hw.ejectValue == 245);
  p.advanceTo(restartAt + 65000);
  CHECK(p.hw.ejectValue == 155 && p.ejectCommandsAt(155) == 2 && p.hw.feedValue == 0);
  p.advanceTo(restartAt + 145000);
  CHECK(p.controller.stage() == Stage::Feeding && p.hw.feedValue == 175);
}

static void configurableStartDuration(uint16_t startMs) {
  ++cases;
  Pipeline p(245, 155, startMs);
  p.startSpinUp();
  const uint64_t changeAt = p.now + uint64_t(startMs) * 1000;
  if (startMs) {
    p.advanceTo(changeAt - 1000);
    CHECK(p.hw.ejectValue == 245 && p.hw.feedValue == 0);
    p.advanceTo(changeAt);
  }
  CHECK(p.ejectCommandsAt(245) == (startMs ? 1U : 0U));
  CHECK(p.hw.ejectValue == 155 && p.ejectCommandsAt(155) == 1);
  p.advanceTo(changeAt + 79000);
  CHECK(p.controller.stage() == Stage::SpinUp && p.hw.feedValue == 0);
  p.advanceTo(changeAt + 80000);
  CHECK(p.controller.stage() == Stage::Feeding && p.hw.feedValue == 175);
}

static void unexpectedCardDuringSpinUpDoesNotSelectSecondGear() {
  ++cases;
  Pipeline p;
  p.startSpinUp();
  const uint64_t highAt = p.now + 50;
  p.rawAt(true, highAt);
  p.advanceTo(highAt + 5000);
  CHECK(p.controller.error() == Error::None);
  CHECK(p.controller.stage() == Stage::SpinUp && p.controller.done() == 0);
  CHECK(p.controller.unexpectedExit().lastStage == Stage::SpinUp && p.controller.unexpectedExit().count == 1);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 255);
  CHECK(p.ejectCommandsAt(200) == 0 && p.negativeCommands() == 0);
  // A lasting obstruction still prevents starting a feed into an occupied outlet.
  p.advanceTo(highAt + 200000);
  CHECK(p.controller.error() == Error::OutletBlocked && p.controller.done() == 0);
}

static void delayedConsumerCountsOnePulse(uint32_t widthUs, uint32_t delayUs) {
  ++cases;
  Pipeline p;
  p.startFeeding();
  const uint64_t highAt = p.now + 50;
  const uint64_t lowAt = highAt + widthUs;
  p.rawAt(true, highAt, false);
  p.rawAt(false, lowAt, false);
  p.advanceTo(lowAt + delayUs, false);
  CHECK(p.qualifiedEvents == 2 && p.queued.size() == 2 && !p.overflow);
  CHECK(p.queued[0].blocked && p.queued[0].us == uint32_t(highAt));
  CHECK(!p.queued[1].blocked && p.queued[1].us == uint32_t(lowAt));
  CHECK(p.controller.done() == 0 && p.controller.stage() == Stage::Feeding);
  p.consume();
  CHECK(p.controller.done() == 1 && p.controller.playerCount(0) == 1);
  CHECK(p.controller.stage() == Stage::Tail && p.controller.error() == Error::None);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 200);
  CHECK(p.negativeCommands() == 1);
  CHECK(p.hw.moves == 1);
  p.advanceTo(p.now + 10000);
  CHECK(p.controller.done() == 1 && p.hw.feedValue == 0);
}

static void liveLongPulseStopsReverseBeforeCardClears() {
  ++cases;
  Pipeline p;
  p.startFeeding();
  const uint64_t highAt = p.now + 50;
  p.rawAt(true, highAt);
  p.advanceTo(highAt + 5000);
  CHECK(p.controller.stage() == Stage::Exiting && p.hw.feedValue == -175);
  CHECK(p.hw.ejectValue == 200 && p.controller.done() == 0 && p.hw.moves == 1);
  p.advanceTo(highAt + 60000);
  CHECK(p.controller.stage() == Stage::Exiting && p.hw.feedValue == 0);
  CHECK(p.hw.ejectValue == 200 && p.controller.done() == 0);
  p.rawAt(false, highAt + 100000);
  p.advanceTo(highAt + 113000);
  CHECK(p.controller.stage() == Stage::Tail && p.controller.done() == 1);
  CHECK(p.hw.feedValue == 0 && p.negativeCommands() == 1);
}

static void exactMinimumPulseEndsBetweenTimerPolls() {
  ++cases;
  Pipeline p;
  p.startFeeding();
  const uint64_t highAt = p.now + 50;
  const uint64_t lowAt = highAt + 1500;
  p.rawAt(true, highAt, false);
  p.advanceTo(lowAt - 1, false);
  CHECK(p.qualifiedEvents == 0);
  // Last timer poll saw only 1450 us high. The CHANGE observation at the
  // falling edge must preserve the old 1500 us candidate before replacing it.
  p.rawAt(false, lowAt, false);
  CHECK(p.qualifiedEvents == 1 && p.queued.size() == 1);
  CHECK(p.queued[0].blocked && p.queued[0].us == uint32_t(highAt));
  p.advanceTo(lowAt + 12100, false);
  CHECK(p.qualifiedEvents == 2 && p.queued.size() == 2);
  p.consume();
  CHECK(p.controller.done() == 1 && p.controller.stage() == Stage::Tail);
  CHECK(p.controller.error() == Error::None && p.hw.feedValue == 0);
  CHECK(p.negativeCommands() == 1);
}

static void realQualifiedHistoryOverflowStopsEverything() {
  ++cases;
  Pipeline p;
  p.startFeeding();
  const uint64_t begin = p.now + 100;
  for (uint64_t cycle = 0; cycle < 20; ++cycle) {
    const uint64_t at = begin + cycle * 15000;
    p.rawAt(true, at, false);
    p.rawAt(false, at + 2000, false);
    p.advanceTo(at + 14100, false);
  }
  CHECK(p.qualifiedEvents == 40 && p.maximumQueued == 31 && p.overflow);
  CHECK(p.hw.feedValue == 175 && p.hw.ejectValue == 200);
  p.consume();
  CHECK(p.controller.error() == Error::SensorOverflow);
  CHECK(p.controller.stage() == Stage::Fault && p.controller.done() == 0);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 0 && !p.hw.holding);
  CHECK(p.ejectCommandsAt(200) == 1);
  CHECK(p.queued.empty());
  p.advanceTo(p.now + 10000);
  CHECK(p.controller.stage() == Stage::Fault);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 0);
}

static void flutteringTrailingEdgeIsOneCard(bool delayedConsumer) {
  ++cases;
  Pipeline p;
  p.startFeeding();
  const bool consume = !delayedConsumer;
  const uint64_t beamAt = p.now + 50;
  p.rawAt(true, beamAt, consume);
  p.rawAt(false, beamAt + 10000, consume);
  p.rawAt(true, beamAt + 18000, consume);   // An 8 ms glimpse used to count the card.
  p.rawAt(false, beamAt + 24000, consume);
  p.rawAt(true, beamAt + 35999, consume);   // At 11.999 ms it is still the same card.
  p.rawAt(false, beamAt + 46000, consume);
  p.advanceTo(beamAt + 58200, consume);
  p.consume();
  CHECK(p.controller.stage() == Stage::Tail && p.controller.done() == 1);
  CHECK(p.qualifiedEvents == 2 && p.negativeCommands() == 1 && p.hw.moves == 1);

  // An extra qualified leading edge during the tail is logged without counting it.
  p.rawAt(true, p.now + 1000);
  p.advanceTo(p.now + 2000);
  CHECK(p.controller.error() == Error::None);
  CHECK(p.controller.unexpectedExit().count == 1 && p.controller.unexpectedExit().lastStage == Stage::Tail);
  CHECK(p.controller.stage() == Stage::Tail && p.controller.done() == 1);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 200 && p.hw.holding);
}

static void twoSeparateCardsQueuedTogetherCountOnceAndWarn() {
  ++cases;
  Pipeline p;
  p.startFeeding();
  const uint64_t beamAt = p.now + 50;
  p.rawAt(true, beamAt, false);
  p.rawAt(false, beamAt + 9000, false);
  p.rawAt(true, beamAt + 21000, false);   // Exactly 12 ms with the outlet clear.
  p.rawAt(false, beamAt + 22500, false);  // Second pulse is only 1.5 ms.
  p.advanceTo(beamAt + 34700, false);
  CHECK(!p.hw.rawBlocked && p.queued.size() == 4);
  p.consume();
  CHECK(p.controller.error() == Error::None && p.controller.stage() == Stage::Tail);
  CHECK(p.controller.unexpectedExit().lastStage == Stage::Tail && p.controller.unexpectedExit().count == 1);
  CHECK(p.controller.done() == 1 && p.negativeCommands() == 1 && p.hw.moves == 1);
  CHECK(p.hw.feedValue == 0 && p.hw.ejectValue == 200 && p.hw.holding);
}

int main() {
  configurableStartDuration(0);
  configurableStartDuration(1);
  configurableStartDuration(500);
  twoSeparateCardsQueuedTogetherCountOnceAndWarn();
  flutteringTrailingEdgeIsOneCard(false);
  flutteringTrailingEdgeIsOneCard(true);
  motorPwmNoiseDoesNotBecomeCards();
  timedEjectionKeepsSpeedThroughSensorEdgesAndRestartsAfterPause();
  unexpectedCardDuringSpinUpDoesNotSelectSecondGear();
  delayedConsumerCountsOnePulse(8000, 20000);
  delayedConsumerCountsOnePulse(100000, 120000);
  liveLongPulseStopsReverseBeforeCardClears();
  exactMinimumPulseEndsBetweenTimerPolls();
  realQualifiedHistoryOverflowStopsEverything();
  std::printf("PASS exit pipeline: %u cases, %u checks\n", cases, checks);
}
