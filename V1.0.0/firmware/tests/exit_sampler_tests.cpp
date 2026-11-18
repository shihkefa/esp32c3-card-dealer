#include "ExitQualifier.h"
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>

static unsigned checks = 0;
static unsigned cases = 0;
#define CHECK(condition) do { \
  ++checks; \
  if (!(condition)) { \
    std::fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #condition); \
    std::exit(1); \
  } \
} while (0)

struct Publication {
  uint32_t publishedUs;
  ExitEdge edge;
};

struct Probe {
  ExitQualifier qualifier;
  std::vector<Publication> published;

  void reset(bool blocked, uint32_t us) {
    qualifier.reset(blocked, us);
    published.clear();
  }
  bool observe(bool blocked, uint32_t us) {
    ExitEdge event{0xA5A55A5AU, true};
    const bool ready = qualifier.observe(blocked, us, event);
    if (ready) published.push_back(Publication{us, event});
    else CHECK(event.us == 0xA5A55A5AU && event.blocked);
    return ready;
  }
  bool poll(uint32_t us) {
    ExitEdge event{0xA5A55A5AU, true};
    const bool ready = qualifier.poll(us, event);
    if (ready) published.push_back(Publication{us, event});
    else CHECK(event.us == 0xA5A55A5AU && event.blocked);
    return ready;
  }
};

static void startupAndReset() {
  ++cases;
  Probe p;
  p.reset(false, 0);
  CHECK(!p.poll(100000));
  CHECK(p.published.empty());
  p.reset(true, 200000);
  CHECK(!p.observe(true, 200100));
  CHECK(!p.poll(300000));
  CHECK(p.published.empty());
  CHECK(!p.observe(false, 300100));
  CHECK(!p.poll(312099));
  CHECK(p.poll(312100));
  CHECK(p.published.size() == 1);
  CHECK(!p.published[0].edge.blocked && p.published[0].edge.us == 300100);
  p.reset(false, 400000);
  CHECK(!p.poll(500000));
  CHECK(p.published.empty());
}

static void alternatingHundredMicrosecondNoise() {
  ++cases;
  Probe p;
  p.reset(false, 0);
  for (uint32_t i = 1; i <= 1000; ++i) {
    const uint32_t at = i * 100;
    CHECK(!p.observe((i & 1U) != 0, at));
    CHECK(!p.poll(at));
    CHECK(!p.poll(at + 50));
  }
  CHECK(!p.poll(200000));
  CHECK(p.published.empty());
}

static void pwmSynchronousNoiseStillNeedsRawObservations() {
  ++cases;
  Probe p;
  p.reset(false, 0);
  // A 2 us glitch every 50 us is high at every 100 us poll. A sampler that only
  // reads those polls would see constant high. Raw falling edges prevent that
  // alias from qualifying here. The electrical CHANGE ISR still has this load.
  for (uint32_t at = 0; at < 50000; at += 50) {
    CHECK(!p.observe(true, at));
    if (at % 100 == 0) CHECK(!p.poll(at));
    CHECK(!p.observe(false, at + 2));
  }
  CHECK(!p.poll(100000));
  CHECK(p.published.empty());
}

static void exactThresholdsAtRawTransitions() {
  ++cases;
  Probe p;
  p.reset(false, 0);
  CHECK(!p.observe(true, 100));
  CHECK(!p.poll(1599));
  // Settling before observing the falling edge preserves a 1500 us pulse.
  CHECK(p.observe(false, 1600));
  CHECK(p.published.size() == 1);
  CHECK(p.published[0].edge.blocked && p.published[0].edge.us == 100);
  CHECK(!p.poll(13599));
  // A 12 ms clear interval can likewise finish on a rising raw edge.
  CHECK(p.observe(true, 13600));
  CHECK(p.published.size() == 2);
  CHECK(!p.published[1].edge.blocked && p.published[1].edge.us == 1600);
  CHECK(!p.poll(15099));
  CHECK(p.poll(15100));
  CHECK(p.published[2].edge.blocked && p.published[2].edge.us == 13600);
  CHECK(!p.poll(15200));

  Probe shortPulse;
  shortPulse.reset(false, 0);
  CHECK(!shortPulse.observe(true, 100));
  CHECK(!shortPulse.observe(false, 1599));
  CHECK(!shortPulse.poll(10000));
  CHECK(shortPulse.published.empty());
}

static void validShortAndLongPulses() {
  ++cases;
  Probe shortPulse;
  shortPulse.reset(false, 0);
  CHECK(!shortPulse.observe(true, 2000));
  CHECK(shortPulse.poll(3500));
  CHECK(!shortPulse.observe(false, 10000));
  CHECK(shortPulse.poll(22000));
  CHECK(shortPulse.published.size() == 2);
  CHECK(shortPulse.published[0].edge.us == 2000);
  CHECK(shortPulse.published[1].edge.us == 10000);

  Probe longPulse;
  longPulse.reset(false, 0);
  CHECK(!longPulse.observe(true, 100));
  CHECK(longPulse.poll(1600));
  for (uint32_t at = 1700; at <= 100000; at += 100) {
    CHECK(!longPulse.poll(at));
  }
  CHECK(!longPulse.observe(false, 100100));
  CHECK(longPulse.poll(112100));
  CHECK(longPulse.published.size() == 2);
  CHECK(longPulse.published[0].edge.blocked);
  CHECK(!longPulse.published[1].edge.blocked);
}

static void bounceReturnsToOriginalState() {
  ++cases;
  Probe p;
  p.reset(false, 0);
  CHECK(!p.observe(true, 100));
  CHECK(!p.observe(false, 800));
  CHECK(!p.poll(5000));
  CHECK(p.published.empty());

  // A later candidate must earn its own complete dwell time.
  CHECK(!p.observe(true, 5100));
  CHECK(!p.poll(6599));
  CHECK(p.poll(6600));
  CHECK(p.published[0].edge.us == 5100);
  CHECK(!p.observe(false, 7000));
  CHECK(!p.observe(true, 9999));
  CHECK(!p.poll(15000));
  CHECK(p.published.size() == 1);
  CHECK(!p.observe(false, 15100));
  CHECK(p.poll(27100));
  CHECK(p.published.size() == 2);
  CHECK(p.published[1].edge.us == 15100);
}

static void duplicateInterruptsDoNotRestartCandidate() {
  ++cases;
  Probe p;
  p.reset(false, 0);
  CHECK(!p.observe(true, 100));
  CHECK(!p.observe(true, 400));
  CHECK(!p.observe(true, 1000));
  CHECK(p.observe(true, 1600));
  CHECK(p.published.size() == 1);
  CHECK(p.published[0].edge.us == 100);
  CHECK(!p.poll(1600));
}

static void microsecondClockWrap() {
  ++cases;
  const uint32_t start = UINT32_MAX - 1000U;
  const uint32_t highAt = start + 100U;
  const uint32_t lowAt = highAt + 1700U;
  Probe p;
  p.reset(false, start);
  CHECK(!p.observe(true, highAt));
  CHECK(!p.poll(highAt + 1499U));
  CHECK(p.poll(highAt + 1500U));
  CHECK(p.published[0].edge.us == highAt);
  CHECK(!p.observe(false, lowAt));
  CHECK(!p.poll(lowAt + 11999U));
  CHECK(p.poll(lowAt + 12000U));
  CHECK(p.published.size() == 2);
  CHECK(p.published[1].edge.us == lowAt);
}

static void qualifiedQueueInputRate() {
  ++cases;
  Probe p;
  p.reset(false, 0);
  // Fastest legal alternating dwell times: one blocked/clear pair per 13.5 ms.
  // A caller must still fault on a genuinely full qualified-event queue; the
  // qualifier neither enlarges that queue nor silently discards valid events.
  for (uint32_t cycle = 0; cycle < 100; ++cycle) {
    const uint32_t at = 100 + cycle * 13500;
    p.observe(true, at);
    CHECK(!p.poll(at));
    CHECK(p.observe(false, at + 1500));
    CHECK(!p.poll(at + 1500));
  }
  CHECK(p.poll(1350100));
  CHECK(p.published.size() == 200);
  for (size_t i = 0; i < p.published.size(); ++i) {
    CHECK(p.published[i].edge.blocked == ((i & 1U) == 0));
    if (i != 0) {
      const uint32_t separation = p.published[i].publishedUs - p.published[i - 1].publishedUs;
      CHECK(separation == (p.published[i].edge.blocked ? 1500U : 12000U));
    }
  }
}

int main() {
  startupAndReset();
  alternatingHundredMicrosecondNoise();
  pwmSynchronousNoiseStillNeedsRawObservations();
  exactThresholdsAtRawTransitions();
  validShortAndLongPulses();
  bounceReturnsToOriginalState();
  duplicateInterruptsDoNotRestartCandidate();
  microsecondClockWrap();
  qualifiedQueueInputRate();
  std::printf("PASS exit qualifier: %u cases, %u checks\n", cases, checks);
}
