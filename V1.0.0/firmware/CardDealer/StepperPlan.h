#pragma once
#include <stdint.h>
#include "MotionLimits.h"
#ifndef DEALER_IRAM
#define DEALER_IRAM
#endif

namespace dealer {
// Integer-only 100us motion scheduler. Caller protects start/stop/snapshot
// against the ISR. No I2C, allocation, floating point or delays in tick().
static_assert(kMaxYawRate<=10000, "100us scheduler can emit at most one half-step per tick");
static_assert(uint64_t(kMaxYawRate)*1000*100+999999999<=UINT32_MAX, "Phase accumulator must fit uint32_t");
static_assert(uint64_t(kMaxYawRate)*kMaxYawRate<=UINT32_MAX, "Braking square must fit uint32_t");
class StepperPlan {
 public:
  // The next move starts at the current electrical phase, even if coils are held.
  void setCounterclockwise(bool enabled) {counterclockwise_=enabled;}
  bool start(int32_t target, uint16_t speed, uint16_t accel) {
    const int64_t distance=int64_t(target)-position_;
    if (busy_ || speed<50 || speed>kMaxYawRate || accel<50 || accel>kMaxYawAcceleration ||
        distance>1000000 || distance< -1000000) return false;
    goal_=target; direction_=distance>=0 ? 1 : -1;
    phaseIncrement_=counterclockwise_?-direction_:direction_;
    maxQ_=uint32_t(speed)*1000; accel_=accel;
    incrementQ_=(uint32_t(accel)+5)/10;
    speedQ_=50000; accumulator_=0; busy_=distance!=0;
    return true;
  }
  void DEALER_IRAM stop() {busy_=false; goal_=position_; speedQ_=0; accumulator_=0;}
  // Move the end point into the current braking ramp without resetting speed or phase.
  void brake() {
    if (!busy_) return;
    const uint32_t v=(speedQ_+999)/1000;
    const int32_t stopping=int32_t((v*v-2500)/(uint32_t(accel_)*2)+1);
    const int32_t remaining=(goal_-position_)*direction_;
    if (stopping<remaining) goal_=position_+stopping*direction_;
  }
  bool DEALER_IRAM tick() {
    if (!busy_) return false;
    const int32_t delta=goal_-position_;
    const uint32_t remain=delta>=0 ? uint32_t(delta) : uint32_t(-delta);
    const uint32_t v=(speedQ_+999)/1000;
    const uint32_t brake=(v*v-2500)/(uint32_t(accel_)*2)+1;
    if (remain<=brake) speedQ_=speedQ_>50000+incrementQ_ ? speedQ_-incrementQ_ : 50000;
    else speedQ_=speedQ_+incrementQ_ < maxQ_ ? speedQ_+incrementQ_ : maxQ_;
    accumulator_=accumulator_+speedQ_*100;
    if (accumulator_<1000000000UL) return false;
    accumulator_=accumulator_-1000000000UL;
    position_=position_+direction_;
    phase_=uint8_t((int(phase_)+phaseIncrement_+8)&7);
    if (position_==goal_) {busy_=false; speedQ_=0; accumulator_=0;}
    return true;
  }
  int32_t position() const {return position_;}
  bool busy() const {return busy_;}
  uint32_t plannedMilliStepsPerSecond() const {return speedQ_;}
  uint8_t DEALER_IRAM phase() const {return phase_;}
 private:
  volatile int32_t position_=0, goal_=0;
  volatile int8_t direction_=1,phaseIncrement_=1;
  bool counterclockwise_=false;
  volatile uint8_t phase_=0;
  volatile bool busy_=false;
  volatile uint32_t speedQ_=0, maxQ_=600000, incrementQ_=30, accumulator_=0;
  volatile uint16_t accel_=300;
};
}
