#include "DealerCore.h"
#include "ExitQualifier.h"
#include <limits.h>
#include <math.h>
#include <string.h>

namespace dealer {
// Let the eject roller settle at the running PWM before feeding the card.
constexpr uint32_t kEjectSettleMs=80;
static uint32_t elapsed(uint32_t now,uint32_t then) {return uint32_t(now-then);}
uint16_t totalCards(const Settings& s) {return uint16_t(s.players)*s.cards+s.remainder;}
static bool validReleaseTrim(int16_t trimMs) {
  return trimMs>=-kMaxReleaseTrimMs && trimMs<=kMaxReleaseTrimMs && trimMs%kTrimStepMs==0;
}
bool validSettings(const Settings& s) {
  return (s.players==3||s.players==4) && s.cards>=1 && s.cards<=36 && s.remainder<=54 &&
    totalCards(s)<=kCapacity && uint8_t(s.profile)<=uint8_t(Profile::Custom) &&
    s.feedPwm>=40 && s.ejectPwm>=40 && s.ejectStartPwm>=40 && s.ejectStartMs<=kMaxEjectStartMs &&
    (s.reversePwm==0 || s.reversePwm>=40) &&
    (s.reverseMs==0 || (s.reverseMs>=10 && s.reverseMs<=300)) &&
    s.maxStepRate>=kMinYawRate && s.maxStepRate<=kMaxYawRate &&
    s.acceleration>=100 && s.acceleration<=kMaxYawAcceleration &&
    validReleaseTrim(s.releaseTrimMs) &&
    s.turnQ16>=6000UL*65536UL && s.turnQ16<=10000UL*65536UL;
}
void applyProfile(Settings& s,Profile p) {
  s.profile=p;
  switch(p) {
    case Profile::Landlord:s.players=3;s.cards=17;s.remainder=3;break;
    case Profile::Guandan:s.players=4;s.cards=27;s.remainder=0;break;
    case Profile::Four13:s.players=4;s.cards=13;s.remainder=0;break;
    case Profile::Three13:s.players=3;s.cards=13;s.remainder=13;break;
    default:break;
  }
}
int32_t plannedTarget(const Settings& s,int32_t origin,uint16_t ordinal) {
  if (!validSettings(s) || ordinal>=totalCards(s)) return INT32_MIN;
  int64_t numerator,denominator;
  if (ordinal<uint16_t(s.players)*s.cards) {
    numerator=int64_t(ordinal)*s.turnQ16;denominator=int64_t(s.players)*65536;
  } else {
    // Targets are distances along the selected direction. After the last
    // regular card the midpoint is cards+1/(2*players) turns from the origin.
    numerator=int64_t(2*s.players*s.cards+1)*s.turnQ16;
    denominator=int64_t(2*s.players)*65536;
  }
  const int64_t target=int64_t(origin)+(numerator+denominator/2)/denominator;
  return target>INT32_MAX || target<INT32_MIN+1 ? INT32_MIN : int32_t(target);
}
static void put16(uint8_t* p,uint16_t v) {p[0]=uint8_t(v);p[1]=uint8_t(v>>8);}
static void put32(uint8_t* p,uint32_t v) {for(uint8_t i=0;i<4;++i)p[i]=uint8_t(v>>(8*i));}
static uint16_t get16(const uint8_t* p) {return uint16_t(p[0])|(uint16_t(p[1])<<8);}
static uint32_t get32(const uint8_t* p) {uint32_t v=0;for(uint8_t i=0;i<4;++i)v|=uint32_t(p[i])<<(8*i);return v;}
static uint32_t crc32(const uint8_t* p,size_t n) {
  uint32_t v=0xFFFFFFFFUL;
  for(size_t i=0;i<n;++i){v^=p[i];for(uint8_t b=0;b<8;++b)v=(v>>1)^(0xEDB88320UL&uint32_t(-int32_t(v&1)));}
  return ~v;
}
void encodeSettings(const Settings& s,uint8_t out[kSettingsBytes]) {
  memset(out,0,kSettingsBytes);memcpy(out,"CDR8",4);
  out[4]=s.players;out[5]=s.cards;out[6]=s.remainder;out[7]=uint8_t(s.profile);
  out[8]=s.feedPwm;out[9]=s.ejectPwm;out[10]=s.calibrated?1:0;
  // Reuse reserved bytes so older CRC-protected records keep their 32-byte layout.
  const uint8_t trimCode=validReleaseTrim(s.releaseTrimMs)?uint8_t((s.releaseTrimMs+kMaxReleaseTrimMs)/kTrimStepMs):0x7f;
  out[11]=trimCode|(s.continuousYaw?0x80:0);
  put16(out+12,s.maxStepRate);put16(out+14,s.acceleration);put32(out+16,s.turnQ16);
  out[20]=s.reversePwm;out[21]=s.ejectStartPwm;put16(out+22,s.reverseMs);
  put16(out+24,s.ejectStartMs);
  out[26]=s.counterclockwise?1:0;
  put32(out+28,crc32(out,28));
}
bool decodeSettings(const uint8_t* in,size_t size,Settings& result,bool* needsSave) {
  if(needsSave)*needsSave=false;
  if(size!=kSettingsBytes || memcmp(in,"CDR",3)!=0 || in[3]<'1' || in[3]>'8' ||
     get32(in+28)!=crc32(in,28) || in[10]>1)return false;
  Settings s;s.players=in[4];s.cards=in[5];s.remainder=in[6];s.profile=Profile(in[7]);
  s.feedPwm=in[8];s.ejectPwm=in[9];s.calibrated=in[10]!=0;
  s.maxStepRate=get16(in+12);s.acceleration=get16(in+14);s.turnQ16=get32(in+16);
  if(in[3]>='2'){s.reversePwm=in[20];s.reverseMs=get16(in+22);}
  if(in[3]>='3')s.ejectStartPwm=in[21];
  if(in[3]>='5')s.ejectStartMs=get16(in+24);
  if(in[3]=='8'){
    if(in[26]>1 || in[27]!=0)return false;
    s.counterclockwise=in[26]!=0;
  }
  if(in[3]>='6'){
    s.continuousYaw=(in[11]&0x80)!=0;
    s.releaseTrimMs=int16_t(in[11]&0x7f)*kTrimStepMs-kMaxReleaseTrimMs;
    if(in[3]=='6') {
      const uint16_t oldSweepRate=get16(in+26);
      if(oldSweepRate<400 || oldSweepRate>2000 || s.maxStepRate<150 || s.maxStepRate>7200)return false;
      if(s.continuousYaw)s.maxStepRate=oldSweepRate;
    }
  }
  if(!validSettings(s))return false;
  result=s;
  if(needsSave)*needsSave=in[3]<'8';
  return true;
}

Settings Controller::operatingSettings(Settings s) const {
  if(turnIsFixed()) {
    s.turnQ16=fixedTurnQ16_;
    s.calibrated=true;
  }
  return s;
}
void Controller::begin(const Settings& s,bool blocked,bool home,uint32_t ms,uint32_t us) {
  homeFault_={};
  unexpectedExit_={};
  calibrationTrace_={};calibrationIntervals_=0;
  sweep_=flyingCard_=brakingSweep_=false;
  settings_=operatingSettings(validSettings(s)?s:Settings{});exit_.reset(blocked,us);home_.reset(home,us);
  stage_=Stage::Idle;error_=Error::None;enteredMs_=ms;homeEdgePosition_=homeBlockedAt_=hw_.position();reverseActive_=false;
  hw_.feed(0);hw_.eject(0);hw_.stopMotion();hw_.hold(false);
  hw_.setCounterclockwise(settings_.counterclockwise);
}
bool Controller::active() const {return stage_>=Stage::Calibrating && stage_<=Stage::Paused;}
bool Controller::configure(const Settings& s) {
  const Settings next=operatingSettings(s);
  if(active() || !validSettings(next))return false;
  if(next.counterclockwise!=settings_.counterclockwise) {
    if(hw_.moving())return false;
    hw_.setCounterclockwise(next.counterclockwise);
  }
  settings_=next;settingsChanged_=true;return true;
}
bool Controller::outletClear(uint32_t us) const {
  return !hw_.outletRawBlocked() && !exit_.stable() && !exit_.raw() && exit_.sinceRawChange(us)>=20000;
}
void Controller::fail(Error e,uint32_t ms) {
  // Keep the original E07 evidence visible until the operator acknowledges it.
  // All outputs were already stopped when the reference fault was recorded.
  if(stage_==Stage::Fault && error_==Error::HomeMissing)return;
  if(stage_!=Stage::Fault)faultStage_=stage_;
  sweep_=flyingCard_=brakingSweep_=false;
  reverseActive_=false;
  hw_.feed(0);hw_.eject(0);hw_.stopMotion();hw_.hold(false);
  stage_=Stage::Fault;error_=e;enteredMs_=ms;pauseRequested_=false;
}
void Controller::externalFault(Error e,uint32_t ms) {fail(e,ms);}
bool Controller::start(uint32_t ms,uint32_t us) {
  if(active() || stage_==Stage::Fault)return false;
  unexpectedExit_={};
  calibrationTrace_={};calibrationIntervals_=0;
  if(!validSettings(settings_)){fail(Error::InvalidSettings,ms);return false;}
  if(!settings_.calibrated){error_=Error::NeedCalibration;return false;}
  if(!ioOk_){fail(Error::IoFault,ms);return false;}
  if(!outletClear(us)){fail(Error::OutletBlocked,ms);return false;}
  origin_=runStart_=hw_.position();homeBlockedAt_=origin_;homeSeen_=false;
  sweep_=flyingCard_=brakingSweep_=false;stationaryNext_=true;
  phaseErrorSteps_=lapRemainderQ16_=0;releaseEstimateMs_=measuredReleaseMs_=0;
  regularDone_=remainderDone_=0;memset(playerCounts_,0,sizeof(playerCounts_));
  pauseRequested_=false;error_=Error::None;hw_.hold(true);schedule(ms,us);return stage_!=Stage::Fault;
}
bool Controller::calibrate(uint32_t ms,uint32_t us) {
  if(active() || stage_==Stage::Fault)return false;
  unexpectedExit_={};
  calibrationTrace_={};calibrationIntervals_=0;
  if(!ioOk_){fail(Error::IoFault,ms);return false;}
  if(!outletClear(us)){fail(Error::OutletBlocked,ms);return false;}
  const int32_t p=hw_.position();
  if(p>INT32_MAX-100000){fail(Error::MotionFault,ms);return false;}
  hw_.feed(0);hw_.eject(0);hw_.hold(true);
  runStart_=homeBlockedAt_=p;homeSeen_=false;
  // A level already present at the start is not a new reference crossing.
  home_.reset(home_.raw(),us);
  calMin_=0xFFFFFFFFUL;calMax_=0;error_=Error::None;enteredMs_=ms;
  stage_=Stage::Calibrating;
  if(!hw_.moveTo(p+72000,400,200)){fail(Error::MotionFault,ms);return false;}
  return true;
}
// Elapsed seconds at a commanded position on the symmetric acceleration / cruise /
// braking profile. A target near the first or last player may lie on either ramp.
float Controller::sweepTimeAt(int32_t position) const {
  const float distance=float(sweepEnd_-sweepStart_);
  const float travelled=float(position-sweepStart_);
  const float accel=settings_.acceleration;
  constexpr float initial=50.0f; // same launch speed as StepperPlan
  const float peak=fminf(settings_.maxStepRate,sqrtf(initial*initial+accel*distance));
  const float ramp=(peak-initial)*(peak+initial)/(2*accel);
  const float rampTime=(peak-initial)/accel;
  if(travelled<ramp)return (sqrtf(initial*initial+2*accel*travelled)-initial)/accel;
  if(distance-travelled>=ramp)return rampTime+(travelled-ramp)/peak;
  const float total=2*rampTime+(distance-2*ramp)/peak;
  return total-(sqrtf(initial*initial+2*accel*(distance-travelled))-initial)/accel;
}
int32_t Controller::timeToPlayerMs() const {
  const int32_t position=hw_.position();
  return int32_t(lroundf(1000.0f*(sweepTimeAt(target_)-sweepTimeAt(position))));
}
int32_t Controller::releaseLeadMs() const {
  return int32_t(releaseEstimateMs_)+settings_.releaseTrimMs;
}
void Controller::brakeSweep(uint32_t ms) {
  hw_.feed(0);hw_.eject(0);hw_.brakeMotion();
  flyingCard_=false;brakingSweep_=true;
  stage_=Stage::Positioning;enteredMs_=ms;
  moveLimitMs_=uint32_t(settings_.maxStepRate)*1000/settings_.acceleration+2500;
}
void Controller::schedule(uint32_t ms,uint32_t us) {
  reverseActive_=false;
  if(done()>=totalCards(settings_)) {
    hw_.feed(0);hw_.eject(0);stage_=Stage::Complete;enteredMs_=ms;pauseRequested_=false;return;
  }
  if(!outletClear(us)){fail(Error::OutletBlocked,ms);return;}
  if(pauseRequested_) {
    if(sweep_)brakeSweep(ms);
    else {stage_=Stage::Paused;enteredMs_=ms;hw_.feed(0);hw_.eject(0);}
    return;
  }
  target_=plannedTarget(settings_,origin_,done());
  if(target_==INT32_MIN){fail(Error::MotionFault,ms);return;}
  const int32_t current=hw_.position();
  const int64_t diff=int64_t(target_)-current;
  // A slow card may have taken the entire interval to the following player.
  // Approach that unserved seat on a new lap after slowing to rest.
  if(diff<0 && sweep_){brakeSweep(ms);return;}
  if(diff<0 || diff>1000000){fail(Error::MotionFault,ms);return;}
  const uint16_t rate=settings_.maxStepRate;
  const uint16_t accel=settings_.acceleration;
  moveLimitMs_=uint32_t(diff*1000/rate)+uint32_t(rate)*2000/accel+2500;
  hw_.feed(0);hw_.eject(0);stage_=Stage::Positioning;enteredMs_=ms;
  if(settings_.continuousYaw && !stationaryNext_ && !sweep_ && done()<uint16_t(settings_.players)*settings_.cards) {
    // One motion, ending at the last player or at the remainder midpoint.
    sweepEnd_=plannedTarget(settings_,origin_,totalCards(settings_)-1);
    if(sweepEnd_==INT32_MIN){fail(Error::MotionFault,ms);return;}
    if(target_<sweepEnd_) {
      sweepStart_=current;
      if(!hw_.moveTo(sweepEnd_,rate,accel)){fail(Error::MotionFault,ms);return;}
      sweep_=true;
    }
  }
  stationaryNext_=false;
  flyingCard_=sweep_ && target_<sweepEnd_;
  if(!sweep_ && !hw_.moveTo(target_,rate,accel))fail(Error::MotionFault,ms);
}
void Controller::spinUp(uint32_t ms) {
  ejectStarting_=settings_.ejectStartMs!=0;
  hw_.feed(0);
  hw_.eject(ejectStarting_?settings_.ejectStartPwm:settings_.ejectPwm);
  stage_=Stage::SpinUp;enteredMs_=ms;
}
void Controller::requestPause() {
  if(stage_>=Stage::Positioning && stage_<=Stage::Tail)pauseRequested_=true;
}
void Controller::reacquireNextCard(uint32_t ms,uint32_t us) {
  if(settings_.continuousYaw) {
    // If deceleration passed the next seat, approach the same seat on the next lap.
    int32_t next=plannedTarget(settings_,origin_,done());
    if(next==INT32_MIN){fail(Error::MotionFault,ms);return;}
    if(next<hw_.position()) {
      const int64_t missingQ16=(int64_t(hw_.position())-next)*65536-lapRemainderQ16_;
      const int64_t laps=(missingQ16+settings_.turnQ16-1)/settings_.turnQ16;
      const int64_t advanceQ16=laps*settings_.turnQ16+lapRemainderQ16_;
      const int64_t steps=(advanceQ16+32768)/65536;
      const int64_t rebased=int64_t(origin_)+steps;
      if(rebased>INT32_MAX){fail(Error::MotionFault,ms);return;}
      origin_=int32_t(rebased);lapRemainderQ16_=int32_t(advanceQ16-steps*65536);
    }
    stationaryNext_=true;
  }
  schedule(ms,us);
}
bool Controller::resume(uint32_t ms,uint32_t us) {
  if(stage_!=Stage::Paused)return false;
  if(!ioOk_){fail(Error::IoFault,ms);return false;}
  pauseRequested_=false;reacquireNextCard(ms,us);return stage_!=Stage::Fault;
}
void Controller::abort(uint32_t ms) {fail(Error::Aborted,ms);}
void Controller::clearFault(uint32_t ms) {
  if(stage_!=Stage::Fault || !ioOk_)return;
  homeFault_={};
  hw_.feed(0);hw_.eject(0);hw_.stopMotion();hw_.hold(false);
  stage_=Stage::Idle;error_=Error::None;enteredMs_=ms;regularDone_=remainderDone_=0;reverseActive_=false;
  memset(playerCounts_,0,sizeof(playerCounts_));pauseRequested_=false;homeSeen_=false;
}
bool Controller::resyncOutlet(bool blocked,uint32_t us) {
  if(stage_!=Stage::Idle)return false;
  exit_.reset(blocked,us);return true;
}
void Controller::stableExit(int8_t edge,uint32_t ms,uint32_t us) {
  if(!edge)return;
  handleExit(edge,ms,us-exit_.sinceRawChange(us),ms,hw_.position());
}
void Controller::qualifiedExitEdge(bool blocked,uint32_t edgeUs,uint32_t edgeMs,int32_t position,uint32_t ms) {
  // The ISR has already confirmed a stable level. Replay the original edge in
  // FIFO order; phase/timing must not include the wait for the qualifier or I2C.
  if(exit_.stable()==blocked)return;
  exit_.reset(blocked,edgeUs);
  handleExit(blocked?1:-1,ms,edgeUs,edgeMs,position);
}
void Controller::handleExit(int8_t edge,uint32_t ms,uint32_t eventUs,uint32_t eventMs,int32_t position) {
  if(edge>0) {
    if(expectsExitBlock(eventUs)) {
      reverseActive_=settings_.reversePwm!=0 && settings_.reverseMs!=0;
      // Send the signed command directly: Hardware inserts its 2ms reversal coast.
      hw_.feed(reverseActive_?-int16_t(settings_.reversePwm):0);
      stage_=Stage::Exiting;enteredMs_=ms;
    }
    else if(active()) {
      if(unexpectedExit_.count<UINT32_MAX)++unexpectedExit_.count;
      unexpectedExit_.lastStage=stage_;
    }
  } else if(stage_==Stage::Exiting) {
    phaseErrorSteps_=position-target_;
    measuredReleaseMs_=uint16_t(elapsed(eventMs,feedStartedMs_));
    // Seed from the stationary first card; follow changes in card drag gradually.
    releaseEstimateMs_=releaseEstimateMs_?uint16_t((3UL*releaseEstimateMs_+measuredReleaseMs_+2)/4):measuredReleaseMs_;
    // One complete blocked -> clear pulse, after input qualification.
    if(regularDone_<uint16_t(settings_.players)*settings_.cards) {
      ++playerCounts_[regularDone_%settings_.players];++regularDone_;
    } else ++remainderDone_;
    reverseActive_=false;hw_.feed(0);stage_=Stage::Tail;enteredMs_=ms;
  }
}
void Controller::rawExitEdge(bool blocked,uint32_t edgeUs,uint32_t ms) {
  stableExit(exit_.settle(edgeUs,ExitQualifier::kBlockedUs,ExitQualifier::kClearUs),ms,edgeUs);
  exit_.observe(blocked,edgeUs);
}
void Controller::stableHome(int8_t edge,uint32_t ms) {
  if(!edge)return;
  const int32_t p=homeEdgePosition_;
  if(edge>0)homeBlockedAt_=p;
  if(edge<0 || !active())return;
  if(stage_==Stage::Calibrating) {
    // Record before validation so the crossing that rejects a run is available.
    calibrationTrace_.samples[calibrationTrace_.count++]={p,homeEdgeMs_};
  }
  if(!homeSeen_) {homeSeen_=true;lastHome_=p;return;}
  const int32_t gap=p-lastHome_;
  if(stage_==Stage::Calibrating) {
    if(gap<6000 || gap>10000){fail(Error::CalibrationFailed,ms);return;}
    if(uint32_t(gap)<calMin_)calMin_=uint32_t(gap);
    if(uint32_t(gap)>calMax_)calMax_=uint32_t(gap);
    lastHome_=p;++calibrationIntervals_;
    if(calibrationIntervals_==kCalibrationSamples-1) {
      if(calMax_-calMin_>20){fail(Error::CalibrationFailed,ms);return;}
      if(!turnIsFixed()) {
        settings_.turnQ16=calibrationTrace_.completeMeanQ16();
        settings_.calibrated=true;settingsChanged_=true;
      }
      hw_.stopMotion();hw_.hold(true);stage_=Stage::Idle;enteredMs_=ms;error_=Error::None;
    }
  } else {
    const int32_t nominal=int32_t((settings_.turnQ16+32768)/65536);
    const int32_t error=gap-nominal;
    if(!turnIsFixed() && (error>24 || error< -24)){fail(Error::HomeMismatch,ms);return;}
    lastHome_=p;
  }
}
void Controller::monitorReference(uint32_t ms) {
  if(!active())return;
  const int32_t p=hw_.position();
  const int32_t limit=stage_==Stage::Calibrating?12000:int32_t((uint64_t(settings_.turnQ16)*6)/(5*65536));
  const int32_t travel=p-(homeSeen_?lastHome_:runStart_);
  if(travel>limit) {
    if(stage_==Stage::Calibrating)fail(Error::CalibrationFailed,ms);
    else {homeFault_={HomeFault::Missing,p,travel};fail(Error::HomeMissing,ms);}
    return;
  }
  const int32_t blockedLimit=int32_t(settings_.turnQ16/(8UL*65536UL));
  const int32_t blockedTravel=p-homeBlockedAt_;
  if(home_.stable() && blockedTravel>blockedLimit) {
    homeFault_={HomeFault::Blocked,p,blockedTravel};fail(Error::HomeMissing,ms);
  }
}
void Controller::tick(uint32_t ms,uint32_t us,bool homeBlocked,bool ioOk,bool overflow,bool homeSampleFresh) {
  ioOk_=ioOk;
  if(overflow){fail(Error::SensorOverflow,ms);return;}
  if(!ioOk) {if(stage_!=Stage::Fault || error_!=Error::IoFault)fail(Error::IoFault,ms);return;}
  stableExit(exit_.settle(us,ExitQualifier::kBlockedUs,ExitQualifier::kClearUs),ms,us);
  if(homeSampleFresh) {
    // Confirm with another actual PCF reading; cached loop values cannot
    // qualify a single-sample spike. Measure the first high sample's position.
    if(homeBlocked && !home_.raw()) {homeEdgePosition_=hw_.position();homeEdgeMs_=ms;}
    home_.observe(homeBlocked,us);
    stableHome(home_.settle(us,1000,1000),ms);
  }
  monitorReference(ms);
  switch(stage_) {
    case Stage::Calibrating:
      if(!hw_.moving())fail(Error::CalibrationFailed,ms);break;
    case Stage::Positioning:
      if(brakingSweep_) {
        if(!hw_.moving()) {
          brakingSweep_=sweep_=false;
          if(pauseRequested_){stage_=Stage::Paused;enteredMs_=ms;}
          else reacquireNextCard(ms,us);
        }
        else if(elapsed(ms,enteredMs_)>moveLimitMs_)fail(Error::MotionFault,ms);
      } else if(sweep_ && pauseRequested_)brakeSweep(ms);
      else if(flyingCard_) {
        if(!hw_.moving() && hw_.position()==sweepEnd_)brakeSweep(ms);
        else if(!hw_.moving() || elapsed(ms,enteredMs_)>moveLimitMs_)fail(Error::MotionFault,ms);
        else if(timeToPlayerMs()<=releaseLeadMs()+settings_.ejectStartMs+int32_t(kEjectSettleMs)) {
          if(!outletClear(us))fail(Error::OutletBlocked,ms);else spinUp(ms);
        }
      } else if(!hw_.moving()) {
        sweep_=false;
        if(hw_.position()!=target_)fail(Error::MotionFault,ms);
        else if(pauseRequested_){stage_=Stage::Paused;enteredMs_=ms;}
        else if(!outletClear(us))fail(Error::OutletBlocked,ms);
        else spinUp(ms);
      } else if(elapsed(ms,enteredMs_)>moveLimitMs_)fail(Error::MotionFault,ms);
      break;
    case Stage::SpinUp:
      if(pauseRequested_){
        if(sweep_)brakeSweep(ms);
        else {hw_.eject(0);stage_=Stage::Paused;enteredMs_=ms;}
      }
      else if(ejectStarting_) {
        if(elapsed(ms,enteredMs_)>=settings_.ejectStartMs) {
          hw_.eject(settings_.ejectPwm);
          ejectStarting_=false;
          enteredMs_=ms;
        }
      } else if(elapsed(ms,enteredMs_)>=kEjectSettleMs && (!flyingCard_ || timeToPlayerMs()<=releaseLeadMs())) {
        if(exit_.stable()) {
          if(exit_.raw() && exit_.sinceRawChange(us)>=20000)fail(Error::OutletBlocked,ms);
          break;
        }
        hw_.feed(settings_.feedPwm);stage_=Stage::Feeding;enteredMs_=feedStartedMs_=ms;feedStartedUs_=us;
      }
      break;
    case Stage::Feeding:if(elapsed(ms,enteredMs_)>1200)fail(Error::NoCard,ms);break;
    case Stage::Exiting:
      if(reverseActive_ && elapsed(ms,enteredMs_)>=settings_.reverseMs) {
        reverseActive_=false;hw_.feed(0);
      }
      if(elapsed(ms,enteredMs_)>1400)fail(Error::CardStuck,ms);break;
    case Stage::Tail:
      if(elapsed(ms,enteredMs_)>=60) {hw_.eject(0);schedule(ms,us);}break;
    case Stage::Idle:case Stage::Complete:
      if(elapsed(ms,enteredMs_)>=1200)hw_.hold(false);break;
    default:break;
  }
}

void Buttons::reset(uint8_t bits,uint32_t ms) {
  for(uint8_t i=0;i<4;++i) {keys_[i]=Key{};keys_[i].raw=keys_[i].down=(bits&(1U<<i))==0;keys_[i].changed=keys_[i].pressed=keys_[i].repeated=ms;}
}
bool Buttons::update(uint8_t bits,uint32_t ms,ButtonEvent& event) {
  for(uint8_t i=0;i<4;++i) {
    Key& k=keys_[i];const bool raw=(bits&(1U<<i))==0;
    if(raw!=k.raw){k.raw=raw;k.changed=ms;}
    if(k.down!=k.raw && elapsed(ms,k.changed)>=30) {
      k.down=k.raw;
      if(k.down){k.pressed=k.repeated=ms;k.longSent=false;}
      else if(!k.longSent){event={Button(i),Press::Short};return true;}
    }
    if(!k.down)continue;
    const uint32_t held=elapsed(ms,k.pressed);
    if((i==0||i==3) && !k.longSent && held>=(i==3?1500U:1000U)) {
      k.longSent=true;event={Button(i),Press::Long};return true;
    }
    if((i==1||i==2) && held>=500 && elapsed(ms,k.repeated)>=120) {
      k.longSent=true;k.repeated=ms;event={Button(i),Press::Repeat};return true;
    }
  }
  return false;
}
const char* errorName(Error e) {
  switch(e) {
    case Error::None:return "NONE";case Error::InvalidSettings:return "SETTINGS";
    case Error::NeedCalibration:return "NEED_CALIBRATION";case Error::OutletBlocked:return "OUTLET_BLOCKED";
    case Error::NoCard:return "NO_CARD";case Error::CardStuck:return "CARD_STUCK";
    case Error::UnexpectedCard:return "UNEXPECTED_CARD";case Error::HomeMissing:return "HOME_MISSING";
    case Error::HomeMismatch:return "HOME_MISMATCH";case Error::IoFault:return "I2C_OR_INIT";
    case Error::SensorOverflow:return "SENSOR_OVERFLOW";case Error::MotionFault:return "MOTION";
    case Error::CalibrationFailed:return "CALIBRATION_FAILED";case Error::Aborted:return "ABORTED";
    case Error::ReleaseWindow:return "RELEASE_WINDOW";
  }return "UNKNOWN";
}
const char* stageName(Stage s) {
  switch(s) {
    case Stage::Idle:return "IDLE";case Stage::Calibrating:return "CALIBRATING";
    case Stage::Positioning:return "POSITIONING";case Stage::SpinUp:return "SPINUP";
    case Stage::Feeding:return "FEEDING";case Stage::Exiting:return "EXITING";
    case Stage::Tail:return "TAIL";case Stage::Paused:return "PAUSED";
    case Stage::Complete:return "COMPLETE";case Stage::Fault:return "FAULT";
  }return "UNKNOWN";
}
}
