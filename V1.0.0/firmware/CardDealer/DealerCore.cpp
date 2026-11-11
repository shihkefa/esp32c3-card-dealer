#include "DealerCore.h"
#include <limits.h>
#include <string.h>

namespace dealer {
static uint32_t elapsed(uint32_t now,uint32_t then) {return uint32_t(now-then);}
uint16_t totalCards(const Settings& s) {return uint16_t(s.players)*s.cards+s.remainder;}
bool validSettings(const Settings& s) {
  return (s.players==3||s.players==4) && s.cards>=1 && s.cards<=36 && s.remainder<=54 &&
    totalCards(s)<=kCapacity && uint8_t(s.profile)<=uint8_t(Profile::Custom) &&
    s.feedPwm>=40 && s.ejectPwm>=40 && s.maxStepRate>=150 && s.maxStepRate<=800 &&
    s.acceleration>=100 && s.acceleration<=1000 &&
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
    // Last regular card is at cards-1/players turns. The next clockwise
    // midpoint between player 1 and 2 is cards+1/(2*players) turns.
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
  memset(out,0,kSettingsBytes);memcpy(out,"CDR1",4);
  out[4]=s.players;out[5]=s.cards;out[6]=s.remainder;out[7]=uint8_t(s.profile);
  out[8]=s.feedPwm;out[9]=s.ejectPwm;out[10]=s.calibrated?1:0;
  put16(out+12,s.maxStepRate);put16(out+14,s.acceleration);put32(out+16,s.turnQ16);
  put32(out+28,crc32(out,28));
}
bool decodeSettings(const uint8_t* in,size_t size,Settings& result) {
  if(size!=kSettingsBytes || memcmp(in,"CDR1",4)!=0 || get32(in+28)!=crc32(in,28) || in[10]>1)return false;
  Settings s;s.players=in[4];s.cards=in[5];s.remainder=in[6];s.profile=Profile(in[7]);
  s.feedPwm=in[8];s.ejectPwm=in[9];s.calibrated=in[10]!=0;
  s.maxStepRate=get16(in+12);s.acceleration=get16(in+14);s.turnQ16=get32(in+16);
  if(!validSettings(s))return false;result=s;return true;
}

void Controller::begin(const Settings& s,bool blocked,bool home,uint32_t ms,uint32_t us) {
  settings_=validSettings(s)?s:Settings{};exit_.reset(blocked,us);home_.reset(home,us);
  stage_=Stage::Idle;error_=Error::None;enteredMs_=ms;homeBlockedAt_=hw_.position();
  hw_.feed(0);hw_.eject(0);hw_.stopMotion();hw_.hold(false);
}
bool Controller::active() const {return stage_>=Stage::Calibrating && stage_<=Stage::Paused;}
bool Controller::configure(const Settings& s) {
  if(active() || !validSettings(s))return false;settings_=s;settingsChanged_=true;return true;
}
bool Controller::outletClear(uint32_t us) const {
  return !exit_.stable() && !exit_.raw() && exit_.sinceRawChange(us)>=20000;
}
void Controller::fail(Error e,uint32_t ms) {
  hw_.feed(0);hw_.eject(0);hw_.stopMotion();hw_.hold(false);
  stage_=Stage::Fault;error_=e;enteredMs_=ms;pauseRequested_=false;
}
void Controller::externalFault(Error e,uint32_t ms) {fail(e,ms);}
bool Controller::start(uint32_t ms,uint32_t us) {
  if(active() || stage_==Stage::Fault)return false;
  if(!validSettings(settings_)){fail(Error::InvalidSettings,ms);return false;}
  if(!settings_.calibrated){error_=Error::NeedCalibration;return false;}
  if(!ioOk_){fail(Error::IoFault,ms);return false;}
  if(!outletClear(us)){fail(Error::OutletBlocked,ms);return false;}
  origin_=runStart_=hw_.position();homeBlockedAt_=origin_;homeSeen_=false;
  regularDone_=remainderDone_=0;memset(playerCounts_,0,sizeof(playerCounts_));
  pauseRequested_=false;error_=Error::None;hw_.hold(true);schedule(ms,us);return stage_!=Stage::Fault;
}
bool Controller::calibrate(uint32_t ms,uint32_t us) {
  if(active() || stage_==Stage::Fault)return false;
  if(!ioOk_){fail(Error::IoFault,ms);return false;}
  if(!outletClear(us)){fail(Error::OutletBlocked,ms);return false;}
  const int32_t p=hw_.position();
  if(p>INT32_MAX-100000){fail(Error::MotionFault,ms);return false;}
  hw_.feed(0);hw_.eject(0);hw_.hold(true);
  runStart_=homeBlockedAt_=p;homeSeen_=false;calibrationIntervals_=0;
  calMin_=0xFFFFFFFFUL;calMax_=0;error_=Error::None;enteredMs_=ms;
  stage_=Stage::Calibrating;
  if(!hw_.moveTo(p+72000,400,200)){fail(Error::MotionFault,ms);return false;}
  return true;
}
void Controller::schedule(uint32_t ms,uint32_t us) {
  if(done()>=totalCards(settings_)) {
    hw_.feed(0);hw_.eject(0);stage_=Stage::Complete;enteredMs_=ms;pauseRequested_=false;return;
  }
  if(!outletClear(us)){fail(Error::OutletBlocked,ms);return;}
  if(pauseRequested_) {stage_=Stage::Paused;enteredMs_=ms;hw_.feed(0);hw_.eject(0);return;}
  target_=plannedTarget(settings_,origin_,done());
  if(target_==INT32_MIN){fail(Error::MotionFault,ms);return;}
  const int64_t diff=int64_t(target_)-hw_.position();
  if(diff<0 || diff>1000000){fail(Error::MotionFault,ms);return;}
  moveLimitMs_=uint32_t(diff*1000/settings_.maxStepRate)+
    uint32_t(settings_.maxStepRate)*2000/settings_.acceleration+2500;
  hw_.feed(0);hw_.eject(0);stage_=Stage::Positioning;enteredMs_=ms;
  if(!hw_.moveTo(target_,settings_.maxStepRate,settings_.acceleration))fail(Error::MotionFault,ms);
}
void Controller::spinUp(uint32_t ms) {
  hw_.feed(0);hw_.eject(settings_.ejectPwm);stage_=Stage::SpinUp;enteredMs_=ms;
}
void Controller::requestPause() {
  if(stage_>=Stage::Positioning && stage_<=Stage::Tail)pauseRequested_=true;
}
bool Controller::resume(uint32_t ms,uint32_t us) {
  if(stage_!=Stage::Paused)return false;
  if(!ioOk_){fail(Error::IoFault,ms);return false;}
  pauseRequested_=false;schedule(ms,us);return stage_!=Stage::Fault;
}
void Controller::abort(uint32_t ms) {fail(Error::Aborted,ms);}
void Controller::clearFault(uint32_t ms) {
  if(stage_!=Stage::Fault || !ioOk_)return;
  hw_.feed(0);hw_.eject(0);hw_.stopMotion();hw_.hold(false);
  stage_=Stage::Idle;error_=Error::None;enteredMs_=ms;regularDone_=remainderDone_=0;
  memset(playerCounts_,0,sizeof(playerCounts_));pauseRequested_=false;homeSeen_=false;
}
void Controller::stableExit(int8_t edge,uint32_t ms) {
  if(!edge)return;
  if(edge>0) {
    if(stage_==Stage::Feeding) {hw_.feed(0);stage_=Stage::Exiting;enteredMs_=ms;}
    else if(active())fail(Error::UnexpectedCard,ms);
  } else if(stage_==Stage::Exiting) {
    // One complete blocked -> clear pulse, after input qualification.
    if(regularDone_<uint16_t(settings_.players)*settings_.cards) {
      ++playerCounts_[regularDone_%settings_.players];++regularDone_;
    } else ++remainderDone_;
    hw_.feed(0);stage_=Stage::Tail;enteredMs_=ms;
  }
}
void Controller::rawExitEdge(bool blocked,uint32_t edgeUs,uint32_t ms) {
  stableExit(exit_.settle(edgeUs,1500,3000),ms);exit_.observe(blocked,edgeUs);
}
void Controller::stableHome(int8_t edge,uint32_t ms) {
  if(!edge)return;
  const int32_t p=hw_.position();
  if(edge>0)homeBlockedAt_=p;
  if(edge<0 || !active())return;
  if(!homeSeen_) {homeSeen_=true;lastHome_=calibrationFirst_=p;return;}
  const int32_t gap=p-lastHome_;
  if(stage_==Stage::Calibrating) {
    if(gap<6000 || gap>10000){fail(Error::CalibrationFailed,ms);return;}
    if(uint32_t(gap)<calMin_)calMin_=uint32_t(gap);
    if(uint32_t(gap)>calMax_)calMax_=uint32_t(gap);
    lastHome_=p;++calibrationIntervals_;
    if(calibrationIntervals_>=4) {
      if(calMax_-calMin_>20){fail(Error::CalibrationFailed,ms);return;}
      settings_.turnQ16=uint32_t((int64_t(p-calibrationFirst_)*65536+2)/4);
      settings_.calibrated=true;settingsChanged_=true;
      hw_.stopMotion();hw_.hold(true);stage_=Stage::Idle;enteredMs_=ms;error_=Error::None;
    }
  } else {
    const int32_t nominal=int32_t((settings_.turnQ16+32768)/65536);
    const int32_t error=gap-nominal;
    if(error>24 || error< -24){fail(Error::HomeMismatch,ms);return;}
    lastHome_=p;
  }
}
void Controller::monitorReference(uint32_t ms) {
  if(!active())return;
  const int32_t p=hw_.position();
  const int32_t limit=stage_==Stage::Calibrating?12000:int32_t((uint64_t(settings_.turnQ16)*6)/(5*65536));
  if(p-(homeSeen_?lastHome_:runStart_)>limit) {fail(stage_==Stage::Calibrating?Error::CalibrationFailed:Error::HomeMissing,ms);return;}
  const int32_t blockedLimit=int32_t(settings_.turnQ16/(8UL*65536UL));
  if(home_.stable() && p-homeBlockedAt_>blockedLimit)fail(Error::HomeMissing,ms);
}
void Controller::tick(uint32_t ms,uint32_t us,bool homeBlocked,bool ioOk,bool overflow) {
  ioOk_=ioOk;
  if(overflow){fail(Error::SensorOverflow,ms);return;}
  if(!ioOk) {if(stage_!=Stage::Fault || error_!=Error::IoFault)fail(Error::IoFault,ms);return;}
  stableExit(exit_.settle(us,1500,3000),ms);
  stableHome(home_.settle(us,1000,1000),ms);home_.observe(homeBlocked,us);
  monitorReference(ms);
  switch(stage_) {
    case Stage::Calibrating:
      if(!hw_.moving())fail(Error::CalibrationFailed,ms);break;
    case Stage::Positioning:
      if(!hw_.moving()) {
        if(hw_.position()!=target_)fail(Error::MotionFault,ms);
        else if(pauseRequested_){stage_=Stage::Paused;enteredMs_=ms;}
        else if(!outletClear(us))fail(Error::OutletBlocked,ms);
        else spinUp(ms);
      } else if(elapsed(ms,enteredMs_)>moveLimitMs_)fail(Error::MotionFault,ms);
      break;
    case Stage::SpinUp:
      if(pauseRequested_){hw_.eject(0);stage_=Stage::Paused;enteredMs_=ms;}
      else if(elapsed(ms,enteredMs_)>=180) {hw_.feed(settings_.feedPwm);stage_=Stage::Feeding;enteredMs_=ms;}
      break;
    case Stage::Feeding:if(elapsed(ms,enteredMs_)>1200)fail(Error::NoCard,ms);break;
    case Stage::Exiting:if(elapsed(ms,enteredMs_)>1400)fail(Error::CardStuck,ms);break;
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
