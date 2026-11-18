#pragma once
#include <stdint.h>
#include <stddef.h>
#include "MotionLimits.h"

namespace dealer {
constexpr uint16_t kCapacity=108;
constexpr uint32_t kNominalTurnQ16=8192UL*65536UL;
// This dealer reported 8191.5000 calibrated half-steps per platter turn over USB.
constexpr uint32_t kDeviceTurnQ16=8191UL*65536UL+32768UL;
constexpr uint16_t kMaxEjectStartMs=500;
constexpr uint16_t kEjectStartStepMs=10;
constexpr int16_t kTrimStepMs=10, kMaxReleaseTrimMs=150;
enum class Profile:uint8_t {Landlord,Guandan,Four13,Three13,Custom};
struct Settings {
  uint8_t players=3, cards=17, remainder=3;
  Profile profile=Profile::Landlord;
  uint8_t feedPwm=175, ejectPwm=200;
  uint8_t ejectStartPwm=255;
  uint16_t ejectStartMs=100;
  uint8_t reversePwm=175;
  uint16_t reverseMs=50;
  uint16_t maxStepRate=kDefaultYawRate, acceleration=kDefaultYawAcceleration;
  uint32_t turnQ16=kNominalTurnQ16;
  bool calibrated=false;
  bool continuousYaw=false;
  bool counterclockwise=false; // Platter direction as viewed from above.
  int16_t releaseTrimMs=0; // A positive trim commands an earlier release.
};
bool validSettings(const Settings& s);
void applyProfile(Settings& s,Profile p);
uint16_t totalCards(const Settings& s);
int32_t plannedTarget(const Settings& s,int32_t origin,uint16_t ordinal);
constexpr size_t kSettingsBytes=32;
void encodeSettings(const Settings& s,uint8_t out[kSettingsBytes]);
bool decodeSettings(const uint8_t* in,size_t size,Settings& result,bool* needsSave=nullptr);

enum class Stage:uint8_t {Idle,Calibrating,Positioning,SpinUp,Feeding,Exiting,Tail,Paused,Complete,Fault};
enum class Error:uint8_t {None,InvalidSettings,NeedCalibration,OutletBlocked,NoCard,CardStuck,
  UnexpectedCard,HomeMissing,HomeMismatch,IoFault,SensorOverflow,MotionFault,CalibrationFailed,Aborted,ReleaseWindow};
enum class HomeFault:uint8_t {None,Missing,Blocked};
struct UnexpectedExitRecord {
  uint32_t count=0;
  Stage lastStage=Stage::Idle;
};
struct HomeFaultRecord {
  HomeFault cause=HomeFault::None;
  int32_t position=0,travel=0;  // Commanded half-steps at the fault.
  const char* label() const {
    switch(cause){case HomeFault::Missing:return "MISS";case HomeFault::Blocked:return "BLOCKED";default:return "";}
  }
};
constexpr uint8_t kCalibrationSamples=5;
struct CalibrationSample {
  int32_t position=0;  // Commanded half-steps at the first fresh high PCF reading.
  uint32_t ms=0;       // millis() at that same reading, modulo 2^32.
};
struct CalibrationTrace {
  uint8_t count=0;
  CalibrationSample samples[kCalibrationSamples]{};
  // Used after all four intervals pass the calibration checks.
  uint32_t completeMeanQ16() const {
    const int64_t total=int64_t(samples[kCalibrationSamples-1].position)-samples[0].position;
    return uint32_t(total*65536/(kCalibrationSamples-1));
  }
};
class Hardware {
 public:
  virtual ~Hardware()=default;
  virtual bool moveTo(int32_t target,uint16_t speed,uint16_t acceleration)=0;
  virtual int32_t position() const=0;
  virtual bool moving() const=0;
  virtual void setCounterclockwise(bool enabled)=0;
  virtual void stopMotion()=0;
  virtual void brakeMotion() {stopMotion();}
  virtual void hold(bool on)=0;
  virtual bool outletRawBlocked() const=0;
  virtual void feed(int16_t pwm)=0;
  virtual void eject(uint8_t pwm)=0;
};

// Settles raw edges at their original micros() timestamps, so an entire valid
// pulse queued while the display is writing is not lost between loop polls.
class StableSignal {
 public:
  void reset(bool v,uint32_t us) {raw_=stable_=v; changed_=us;}
  int8_t settle(uint32_t us,uint32_t highUs,uint32_t lowUs) {
    if (raw_==stable_ || uint32_t(us-changed_)<(raw_?highUs:lowUs)) return 0;
    stable_=raw_; return stable_?1:-1;
  }
  void observe(bool v,uint32_t us) {if (v!=raw_) {raw_=v;changed_=us;}}
  bool stable() const {return stable_;}
  bool raw() const {return raw_;}
  uint32_t sinceRawChange(uint32_t us) const {return uint32_t(us-changed_);}
 private:
  bool raw_=false,stable_=false;
  uint32_t changed_=0;
};

class Controller {
 public:
  explicit Controller(Hardware& hw,uint32_t fixedTurnQ16=0):hw_(hw),fixedTurnQ16_(fixedTurnQ16){}
  void begin(const Settings& settings,bool exitBlocked,bool homeBlocked,uint32_t ms,uint32_t us);
  bool configure(const Settings& settings);
  bool start(uint32_t ms,uint32_t us);
  bool calibrate(uint32_t ms,uint32_t us);
  void requestPause();
  bool resume(uint32_t ms,uint32_t us);
  void abort(uint32_t ms);
  void clearFault(uint32_t ms);
  bool resyncOutlet(bool blocked,uint32_t us);
  void rawExitEdge(bool blocked,uint32_t edgeUs,uint32_t processingMs);
  void qualifiedExitEdge(bool blocked,uint32_t edgeUs,uint32_t edgeMs,int32_t edgePosition,uint32_t processingMs);
  void tick(uint32_t ms,uint32_t us,bool homeBlocked,bool ioOk,bool edgeOverflow=false,bool homeSampleFresh=true);
  void externalFault(Error error,uint32_t ms);
  Stage stage() const {return stage_;}
  Stage faultStage() const {return faultStage_;}
  const HomeFaultRecord& homeFault() const {return homeFault_;}
  const UnexpectedExitRecord& unexpectedExit() const {return unexpectedExit_;}
  bool expectsExitBlock(uint32_t eventUs) const {
    return stage_==Stage::Feeding && int32_t(eventUs-feedStartedUs_)>=0;
  }
  Error error() const {return error_;}
  const Settings& settings() const {return settings_;}
  bool turnIsFixed() const {return fixedTurnQ16_!=0;}
  uint16_t done() const {return regularDone_+remainderDone_;}
  uint16_t regularDone() const {return regularDone_;}
  uint16_t remainderDone() const {return remainderDone_;}
  uint8_t playerCount(uint8_t i) const {return i<4?playerCounts_[i]:0;}
  bool pauseRequested() const {return pauseRequested_;}
  bool exitBlocked() const {return exit_.stable();}
  bool homeBlocked() const {return home_.stable();}
  bool active() const;
  bool settingsChanged() {bool b=settingsChanged_;settingsChanged_=false;return b;}
  uint8_t calibrationTurns() const {return calibrationIntervals_;}
  const CalibrationTrace& calibrationTrace() const {return calibrationTrace_;}
  int32_t target() const {return target_;}
  int32_t phaseErrorSteps() const {return phaseErrorSteps_;}
  uint16_t measuredReleaseMs() const {return measuredReleaseMs_;}
  bool sweeping() const {return sweep_;}
  bool outletClear(uint32_t us) const;
 private:
  Hardware& hw_;
  const uint32_t fixedTurnQ16_;
  Settings operatingSettings(Settings settings) const;
  Settings settings_{};
  Stage stage_=Stage::Idle;
  Stage faultStage_=Stage::Idle;
  HomeFaultRecord homeFault_;
  UnexpectedExitRecord unexpectedExit_;
  Error error_=Error::None;
  StableSignal exit_,home_;
  uint32_t enteredMs_=0, moveLimitMs_=0;
  int32_t origin_=0,target_=0,runStart_=0,lastHome_=0,homeBlockedAt_=0,homeEdgePosition_=0;
  uint16_t regularDone_=0,remainderDone_=0;
  uint8_t playerCounts_[4]={0,0,0,0};
  bool pauseRequested_=false,homeSeen_=false,ioOk_=false,settingsChanged_=false,reverseActive_=false;
  bool ejectStarting_=false;
  bool sweep_=false, flyingCard_=false, brakingSweep_=false, stationaryNext_=true;
  int32_t sweepStart_=0,sweepEnd_=0,phaseErrorSteps_=0;
  int32_t lapRemainderQ16_=0;
  uint32_t feedStartedMs_=0,feedStartedUs_=0;
  uint16_t measuredReleaseMs_=0,releaseEstimateMs_=0;
  float sweepTimeAt(int32_t position) const;
  int32_t timeToPlayerMs() const;
  int32_t releaseLeadMs() const;
  void brakeSweep(uint32_t ms);
  void reacquireNextCard(uint32_t ms,uint32_t us);
  uint8_t calibrationIntervals_=0;
  uint32_t homeEdgeMs_=0;
  CalibrationTrace calibrationTrace_{};
  uint32_t calMin_=0xFFFFFFFFUL,calMax_=0;
  void fail(Error e,uint32_t ms);
  void schedule(uint32_t ms,uint32_t us);
  void spinUp(uint32_t ms);
  void stableExit(int8_t edge,uint32_t ms,uint32_t us);
  void handleExit(int8_t edge,uint32_t processingMs,uint32_t eventUs,uint32_t eventMs,int32_t position);
  void stableHome(int8_t edge,uint32_t ms);
  void monitorReference(uint32_t ms);
};

enum class Button:uint8_t {Set,Minus,Plus,Run};
enum class Press:uint8_t {Short,Long,Repeat};
struct ButtonEvent {Button button;Press press;};
class Buttons {
 public:
  void reset(uint8_t releasedBits,uint32_t ms);
  bool update(uint8_t releasedBits,uint32_t ms,ButtonEvent& event);
 private:
  struct Key {bool raw=false,down=false,longSent=false;uint32_t changed=0,pressed=0,repeated=0;} keys_[4];
};
const char* errorName(Error e);
const char* stageName(Stage s);
}
