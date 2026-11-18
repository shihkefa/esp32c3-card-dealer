#include <Arduino.h>
#include <Wire.h>
#include <Preferences.h>
#include <esp_arduino_version.h>
#include <esp_timer.h>
#include <soc/gpio_struct.h>
#include <hal/gpio_ll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "BoardConfig.h"
#include "DealerCore.h"
#include "Display.h"
#include "EdgeEvent.h"
#include "ExitQualifier.h"
#include "RadioPower.h"
#include "FlightLog.h"
#define DEALER_IRAM IRAM_ATTR
#include "StepperPlan.h"

#if !CONFIG_IDF_TARGET_ESP32C3
#error "Select ESP32C3 Dev Module, not ESP32/ESP32-S3."
#endif
#if ESP_ARDUINO_VERSION_MAJOR < 3
#error "This project requires Arduino-ESP32 3.x (tested with 3.0.5)."
#endif
#if !ARDUINO_USB_CDC_ON_BOOT
#error "Enable USB CDC On Boot. GPIO20/21 are I2C, not UART0."
#endif

static dealer::StepperPlan motion;
static_assert(Board::kStepperTickUs==100,"StepperPlan requires a 100us timer");
static portMUX_TYPE motionMux=portMUX_INITIALIZER_UNLOCKED;
static bool holdCoils=false;
static volatile int32_t sampledCommandPosition=0;
static hw_timer_t* stepTimer=nullptr;
static ExitQualifier exitQualifier;
static volatile bool exitSamplingReady=false;
static void pollQualifiedExit();
// SRAM table: timer ISR remains valid during an idle NVS flash write.
constexpr uint32_t kCoilA=1UL<<Board::kStepperPins[0],kCoilB=1UL<<Board::kStepperPins[1];
constexpr uint32_t kCoilC=1UL<<Board::kStepperPins[2],kCoilD=1UL<<Board::kStepperPins[3];
static DRAM_ATTR uint32_t coilPatterns[8]={kCoilA,kCoilA|kCoilB,kCoilB,kCoilB|kCoilC,
  kCoilC,kCoilC|kCoilD,kCoilD,kCoilD|kCoilA};
constexpr uint32_t kCoilMask=kCoilA|kCoilB|kCoilC|kCoilD;
static void IRAM_ATTR outputPhase() {
  uint8_t p=motion.phase();
  if(Board::kYawElectricalDirection<0)p=uint8_t((8-p)&7);
  const uint32_t mask=holdCoils?coilPatterns[p]:0;
  GPIO.out_w1tc.val=kCoilMask&~mask;GPIO.out_w1ts.val=mask;
}
static void IRAM_ATTR stepTick() {
  portENTER_CRITICAL_ISR(&motionMux);
  if(motion.tick()){outputPhase();sampledCommandPosition=motion.position();}
  portEXIT_CRITICAL_ISR(&motionMux);
  pollQualifiedExit();
}

class ActualHardware final:public dealer::Hardware {
 public:
  bool init() {
    for(uint8_t p:Board::kStepperPins){pinMode(p,OUTPUT);digitalWrite(p,LOW);}
    const uint8_t pins[]={Board::kFeedIn1,Board::kFeedIn2,Board::kEjectIn1};
    pwmReady_=true;
    for(uint8_t p:pins){pinMode(p,OUTPUT);digitalWrite(p,LOW);if(!ledcAttach(p,Board::kPwmHz,8))pwmReady_=false;else ledcWrite(p,0);}
    stepTimer=timerBegin(1000000);
    if(stepTimer){timerAttachInterrupt(stepTimer,stepTick);timerAlarm(stepTimer,Board::kStepperTickUs,true,0);}
    return healthy();
  }
  bool healthy() const {return pwmReady_&&stepTimer!=nullptr;}
  void setCounterclockwise(bool ccw) override {
    portENTER_CRITICAL(&motionMux);motion.setCounterclockwise(ccw);portEXIT_CRITICAL(&motionMux);
  }
  bool moveTo(int32_t target,uint16_t speed,uint16_t accel) override {
    portENTER_CRITICAL(&motionMux);holdCoils=true;outputPhase();
    bool ok=motion.start(target,speed,accel);portEXIT_CRITICAL(&motionMux);return ok;
  }
  int32_t position() const override {
    portENTER_CRITICAL(&motionMux);int32_t p=motion.position();portEXIT_CRITICAL(&motionMux);return p;
  }
  bool moving() const override {
    portENTER_CRITICAL(&motionMux);bool b=motion.busy();portEXIT_CRITICAL(&motionMux);return b;
  }
  void stopMotion() override {portENTER_CRITICAL(&motionMux);motion.stop();portEXIT_CRITICAL(&motionMux);}
  void brakeMotion() override {portENTER_CRITICAL(&motionMux);motion.brake();portEXIT_CRITICAL(&motionMux);}
  void hold(bool on) override {portENTER_CRITICAL(&motionMux);holdCoils=on;outputPhase();portEXIT_CRITICAL(&motionMux);}
  bool outletRawBlocked() const override {
    return (gpio_ll_get_level(&GPIO,Board::kExitPin)!=0)==Board::kExitBlockedHigh;
  }
  void feed(int16_t pwm) override {
    pwm=pwm>255?255:(pwm< -255?-255:pwm);
    if(!pwm){pending_=0;feed_=0;zeroPin(Board::kFeedIn1);zeroPin(Board::kFeedIn2);return;}
    if(feed_ && ((feed_<0)!=(pwm<0))) {applyFeed(0);pending_=pwm;deadAt_=millis();return;}
    if(pending_){pending_=pwm;return;}applyFeed(pwm);
  }
  void eject(uint8_t pwm) override {
    if(!pwm){eject_=0;zeroPin(Board::kEjectIn1);return;}
    if(pwm==eject_)return;
    if(!pwmReady_){forceCoast();return;}
    eject_=pwm;if(!ledcWrite(Board::kEjectIn1,pwm)){pwmReady_=false;forceCoast();}
  }
  void service() {if(pending_ && uint32_t(millis()-deadAt_)>=2){int16_t p=pending_;pending_=0;applyFeed(p);}}
  int16_t feedPwm() const {return feed_;}
  uint8_t ejectPwm() const {return eject_;}
 private:
  bool pwmReady_=false;
  int16_t feed_=0,pending_=0;
  uint8_t eject_=0;
  uint32_t deadAt_=0;
  void zeroPin(uint8_t pin) {
    if(!ledcWrite(pin,0)){pwmReady_=false;ledcDetach(pin);pinMode(pin,OUTPUT);digitalWrite(pin,LOW);}
  }
  void forceCoast() {
    pending_=0;feed_=0;eject_=0;
    zeroPin(Board::kFeedIn1);zeroPin(Board::kFeedIn2);zeroPin(Board::kEjectIn1);
  }
  void applyFeed(int16_t pwm) {
    if(!pwmReady_){forceCoast();return;}
    if(feed_==pwm)return;feed_=pwm;
    // Both outputs coast before reversing; no shoot-through command pair.
    bool ok=ledcWrite(Board::kFeedIn1,0);ok=ledcWrite(Board::kFeedIn2,0)&&ok;
    if(pwm>0)ok=ledcWrite(Board::kFeedIn1,uint8_t(pwm))&&ok;
    if(pwm<0)ok=ledcWrite(Board::kFeedIn2,uint8_t(-pwm))&&ok;
    if(!ok){pwmReady_=false;forceCoast();}
  }
};
static ActualHardware hardware;
static dealer::Controller controller(hardware,dealer::kDeviceTurnQ16);
static DealerDisplay screen;
static dealer::Buttons buttons;
static Preferences preferences;
static bool nvsReady=false,ioHealthy=false,pendingSave=false,advanced=false;
static uint8_t pcfBits=0xFF,field=0,advancedField=0;
static uint32_t pcfAt=0,drawAt=0,recoveryAt=0,editAt=0,noticeAt=0;
static const char* notice=nullptr;
static bool jogActive=false;
static uint32_t jogAt=0,jogDuration=0;

constexpr uint8_t kEdges=32;
static volatile ExitEdge edgeQueue[kEdges];
static volatile int32_t edgePosition[kEdges];
static int32_t candidatePosition=0;
static bool candidateLevel=false;
static volatile uint8_t edgeHead=0,edgeTail=0;
static volatile bool edgeOverflow=false;
static volatile uint32_t exitRawCount=0,exitQualifiedCount=0,exitOverflowCount=0;
static portMUX_TYPE edgeMux=portMUX_INITIALIZER_UNLOCKED;
// Called with edgeMux held; only qualified transitions occupy queue slots.
static void IRAM_ATTR publishExit(const ExitEdge& event) {
  exitQualifiedCount=exitQualifiedCount+1;
  const uint8_t next=uint8_t((edgeHead+1)%kEdges);
  if(next==edgeTail){edgeOverflow=true;exitOverflowCount=exitOverflowCount+1;}
  else{edgeQueue[edgeHead].us=event.us;edgeQueue[edgeHead].blocked=event.blocked;edgePosition[edgeHead]=candidatePosition;edgeHead=next;}
}
static void IRAM_ATTR pollQualifiedExit() {
  if(!exitSamplingReady)return;
  portENTER_CRITICAL_ISR(&edgeMux);
  ExitEdge event;
  if(exitQualifier.poll(uint32_t(esp_timer_get_time()),event))publishExit(event);
  portEXIT_CRITICAL_ISR(&edgeMux);
}
static void IRAM_ATTR exitInterrupt() {
  if(!exitSamplingReady)return;
  portENTER_CRITICAL_ISR(&edgeMux);
  const uint32_t at=uint32_t(esp_timer_get_time());
  const bool blocked=(gpio_ll_get_level(&GPIO,Board::kExitPin)!=0)==Board::kExitBlockedHigh;
  exitRawCount=exitRawCount+1;
  ExitEdge event;
  if(exitQualifier.observe(blocked,at,event))publishExit(event);
  if(candidateLevel!=blocked){candidatePosition=sampledCommandPosition;candidateLevel=blocked;}
  portEXIT_CRITICAL_ISR(&edgeMux);
}
static bool popEdge(ExitEdge& e,int32_t& position) {
  portENTER_CRITICAL(&edgeMux);
  if(edgeTail==edgeHead){portEXIT_CRITICAL(&edgeMux);return false;}
  e.us=edgeQueue[edgeTail].us;e.blocked=edgeQueue[edgeTail].blocked;
  position=edgePosition[edgeTail];
  edgeTail=uint8_t((edgeTail+1)%kEdges);portEXIT_CRITICAL(&edgeMux);return true;
}

// USB logging is buffered and never waits for a USB host or TX buffer space.
static char txQueue[1536];static uint16_t txHead=0,txTail=0;
static size_t txFree(){return (txTail+sizeof(txQueue)-txHead-1)%sizeof(txQueue);}
static void logText(const char* s) {
  while(*s){uint16_t next=(txHead+1)%sizeof(txQueue);if(next==txTail)return;txQueue[txHead]=*s++;txHead=next;}
}
static void flushLog() {
  if(!Serial){txTail=txHead;return;}
  int room=Serial.availableForWrite();if(room<=0)return;
  uint8_t tmp[48];size_t n=0;uint16_t cursor=txTail;
  while(n<sizeof(tmp)&&n<size_t(room)&&cursor!=txHead){tmp[n++]=uint8_t(txQueue[cursor]);cursor=(cursor+1)%sizeof(txQueue);}
  if(n)txTail=(txTail+Serial.write(tmp,n))%sizeof(txQueue);
}
static void showNotice(const char* s) {notice=s;noticeAt=millis();}
static flight::Recorder flightRecorder;
static flight::Report exportBuffer;
static bool flightPending=false,flightRamOnly=false,exporting=false;
static bool calibrationRamOnly=false;
static flight::CalibrationReport calibrationExport;
static bool exportingCalibration=false;
static int exportRow=-2;
static flight::Counters flightCounters(){
  portENTER_CRITICAL(&edgeMux);
  flight::Counters counts{exitRawCount,exitQualifiedCount,exitOverflowCount};
  portEXIT_CRITICAL(&edgeMux);return counts;
}
static bool flightQuiet(){return !controller.active()&&!jogActive&&!hardware.moving()&&!hardware.feedPwm()&&!hardware.ejectPwm();}
static void serviceFlight(){
  static bool sawFault=false;
  const bool fault=controller.stage()==dealer::Stage::Fault;
  if(fault&&!sawFault&&!flightRecorder.recording&&!flightPending){
    flightRecorder.begin(flight::Kind::IdleFault,controller.settings(),millis(),hardware.position(),flightCounters(),controller.homeBlocked());
  }
  sawFault=fault;
  if(flightRecorder.recording){
    flightRecorder.stage(controller,millis());
    if(!controller.active()){
      flight::Result result=flight::Result::Complete;
      if(controller.error()==dealer::Error::Aborted)result=flight::Result::Aborted;
      else if(controller.stage()==dealer::Stage::Fault)result=flight::Result::Fault;
      else if(controller.error()!=dealer::Error::None)result=flight::Result::Rejected;
      flightRecorder.finish(controller,result,millis(),hardware.position(),flightCounters());flightPending=true;
    }
  }
  if(flightPending&&flightQuiet()){
    flightRamOnly=!flight::save(flightRecorder.report);
    const bool wasCalibration=flightRecorder.report.header.kind==flight::Kind::Calibration;
    if(wasCalibration)
      calibrationRamOnly=!flight::saveCalibration(flightRecorder.calibration);
    flightPending=false;
    if(!exporting && Serial){
      logText(flightRamOnly?"LOG RAM ONLY\n":"LOG SAVED\n");
      if(wasCalibration)logText(calibrationRamOnly?"CAL RAM ONLY\n":"CAL SAVED\n");
    }
    showNotice(wasCalibration?(calibrationRamOnly?"CAL RAM ONLY":"CAL SAVED"):(flightRamOnly?"LOG RAM ONLY":"LOG SAVED"));
  }
}
static void recordedStart(bool calibration){
  if(controller.active()||jogActive||controller.stage()==dealer::Stage::Fault)return;
  serviceFlight();flightRamOnly=false;
  flightRecorder.begin(calibration?flight::Kind::Calibration:flight::Kind::Deal,controller.settings(),
                       millis(),hardware.position(),flightCounters(),controller.homeBlocked());
  if(calibration)controller.calibrate(millis(),micros());else controller.start(millis(),micros());
  serviceFlight();
}
static void flightCommand(const char* action,const char* arg){
  if(!action || (strcmp(action,"status")==0 && !arg)){
    char line[144];
    snprintf(line,sizeof(line),"LOG storage=%s stored=%u/4 recording=%u ram_latest=%u export=%u\n",
             flight::storageState(),flight::stored(),flightRecorder.recording,flightRamOnly,exporting);
    logText(line);return;
  }
  if(strcmp(action,"export")!=0 || (arg && (strlen(arg)!=1 || arg[0]<'1' || arg[0]>'4'))){
    logText("USE log status | log export [1..4]\n");return;
  }
  if(!flightQuiet()||exporting){logText("LOG BUSY\n");return;}
  unsigned rank=arg?unsigned(arg[0]-'0'):1;
  if(!flight::loadForExport(rank,flightRamOnly?&flightRecorder.report:nullptr,exportBuffer)){logText("NO SAVED LOG AT THAT RANK\n");return;}
  exportRow=-2;exportingCalibration=false;exporting=true;
}
static void calibrationLogCommand(const char* action,const char* arg) {
  if(!action || (strcmp(action,"status")==0 && !arg)) {
    char line[144];
    snprintf(line,sizeof(line),"CAL storage=%s stored=%u/4 recording=%u ram_latest=%u export=%u\n",
      flight::calibrationStorageState(),flight::calibrationsStored(),controller.active(),calibrationRamOnly,exporting);
    logText(line);return;
  }
  if(strcmp(action,"export")!=0 || (arg && (strlen(arg)!=1 || arg[0]<'1' || arg[0]>'4'))) {
    logText("USE cal status | cal export [1..4]\n");return;
  }
  if(!flightQuiet() || exporting){logText("CAL BUSY\n");return;}
  const unsigned rank=arg?unsigned(arg[0]-'0'):1;
  if(!flight::loadCalibrationForExport(rank,calibrationRamOnly?&flightRecorder.calibration:nullptr,calibrationExport)) {
    logText("NO SAVED CAL AT THAT RANK\n");return;
  }
  exportRow=-2;exportingCalibration=true;exporting=true;
}
static const char* yawDirectionName(const dealer::Settings& s) {
  return s.counterclockwise?"ccw":"cw";
}
static void streamCalibration() {
  const auto& r=calibrationExport;
  char line[522];
  if(exportRow==-2) {
    const auto& h=r.header;
    const char* results[]={"complete","fault","aborted","rejected"};
    const unsigned gaps=r.count>0?r.count-1:0;
    int32_t smallest=INT32_MAX,largest=INT32_MIN;
    for(unsigned i=1;i<r.count;++i){
      const int32_t gap=r.samples[i].position-r.samples[i-1].position;
      if(gap<smallest)smallest=gap;
      if(gap>largest)largest=gap;
    }
    const double mean=gaps?double(r.samples[gaps].position-r.samples[0].position)/gaps:-1.0;
    dealer::Settings s;const bool decoded=dealer::decodeSettings(h.settings,sizeof(h.settings),s);
    snprintf(line,sizeof(line),"# cal=%lu result=%s code=%s usable=%u reference_rate_steps_s=400 reference_accel=200 speed_pct=%u.%02u speed_steps_s=%u yaw_direction=%s accepted_intervals=%u min_steps=%ld max_steps=%ld spread_steps=%ld mean_steps=%.4f elapsed_ms=%lu rows=%u\n",
      (unsigned long)h.sequence,results[unsigned(h.result)],dealer::errorName(h.error),
      unsigned(h.result==flight::Result::Complete && h.error==dealer::Error::None && gaps==4 && h.calibrationTurns==4),
      s.maxStepRate/100,s.maxStepRate%100,s.maxStepRate,decoded?yawDirectionName(s):"-",h.calibrationTurns,
      long(gaps?smallest:-1),long(gaps?largest:-1),long(gaps?largest-smallest:-1),mean,(unsigned long)h.elapsedMs,r.count);
  } else if(exportRow==-1) {
    strcpy(line,"sample,position_step,elapsed_ms,gap_steps,interval_ms\n");
  } else if(exportRow<r.count) {
    const auto& p=r.samples[exportRow];
    const int32_t steps=exportRow?p.position-r.samples[exportRow-1].position:-1;
    const long dt=exportRow?long(p.elapsedMs-r.samples[exportRow-1].elapsedMs):-1L;
    snprintf(line,sizeof(line),"%d,%ld,%lu,%ld,%ld\n",exportRow+1,long(p.position),(unsigned long)p.elapsedMs,long(steps),dt);
  } else {
    snprintf(line,sizeof(line),"# END CAL rows=%u\n",r.count);exporting=false;exportingCalibration=false;
  }
  logText(line);++exportRow;
}
static void streamFlight(){
  if(!exporting)return;
  if(!Serial){exporting=false;return;}
  if(txFree()<896)return;
  if(exportingCalibration){streamCalibration();return;}
  const auto& h=exportBuffer.header;
  char line[896];
  if(exportRow==-2){
    dealer::Settings s;
    const bool decoded=dealer::decodeSettings(h.settings,sizeof(h.settings),s);
    const char* kind=h.kind==flight::Kind::Calibration?"calibration":(h.kind==flight::Kind::Deal?"deal":"idle_fault");
    const char* results[]={"complete","fault","aborted","rejected"};
    const bool hasE06=h.magic!=flight::kLegacyLogMagic;
    char e06Count[12]="-";
    if(hasE06)snprintf(e06Count,sizeof(e06Count),"%lu",(unsigned long)h.unexpectedCount);
    const char* e06Stage=hasE06 && h.unexpectedCount?dealer::stageName(h.unexpectedLastStage):"-";
    snprintf(line,sizeof(line),"# run=%lu kind=%s result=%s code=%s stage=%s start_uptime_ms=%lu elapsed_ms=%lu origin=%ld stop=%ld target=%ld phase_error=%ld regular=%u extra=%u raw=%lu qualified=%lu overflows=%lu home_pulses=%u home_fault=%u home_fault_pos=%ld home_travel=%ld exit_blocked=%u home_blocked=%u cal_turns=%u turn_q16=%lu players=%u cards=%u rest=%u continuous=%u rate=%u speed_pct=%.2f speed_steps_s=%u yaw_direction=%s trim_ms=%d accel=%u max_rate=%u feed_pwm=%u eject1=%u eject_ms=%u eject2=%u reverse=%u reverse_ms=%u e06_count=%s e06_last_stage=%s rows=%u\n",
      (unsigned long)h.sequence,kind,results[unsigned(h.result)],dealer::errorName(h.error),h.result==flight::Result::Complete?"-":dealer::stageName(h.faultStage),
      (unsigned long)h.startMs,(unsigned long)h.elapsedMs,long(h.origin),long(h.stopPosition),long(h.finalTarget),long(h.finalPhaseError),h.regularDone,h.extraDone,
      (unsigned long)h.rawEdges,(unsigned long)h.qualifiedEdges,(unsigned long)h.overflows,h.homePulses,unsigned(h.homeFault),
      long(h.homePosition),long(h.homeTravel),h.exitBlocked,h.homeBlocked,h.calibrationTurns,(unsigned long)h.calibratedTurnQ16,
      s.players,s.cards,s.remainder,unsigned(s.continuousYaw),s.maxStepRate,double(s.maxStepRate)/dealer::kYawRatePerPercent,s.maxStepRate,decoded?yawDirectionName(s):"-",int(s.releaseTrimMs),s.acceleration,s.maxStepRate,
      s.feedPwm,s.ejectStartPwm,s.ejectStartMs,s.ejectPwm,s.reversePwm,s.reverseMs,e06Count,e06Stage,h.rowCount);
  } else if(exportRow==-1){
    strcpy(line,"card,player_0_remainder,target_step,spin_ms,feed_ms,blocked_ms,blocked_step,clear_ms,clear_step,count_ms,phase_error_steps,release_est_ms,qualified_edges\n");
  } else if(exportRow<h.rowCount){
    const auto& r=exportBuffer.rows[exportRow];
    snprintf(line,sizeof(line),"%d,%u,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%u,%u\n",exportRow+1,r.player,
      long(r.target),long(r.spinMs),long(r.feedMs),long(r.blockedMs),long(r.blockedPosition),
      long(r.clearMs),long(r.clearPosition),long(r.countMs),long(r.phaseError),r.releaseMs,r.qualifiedEdges);
  } else {snprintf(line,sizeof(line),"# END LOG rows=%u\n",h.rowCount);exporting=false;}
  logText(line);++exportRow;
}
static bool readPcf(uint8_t& bits) {
  if(Wire.requestFrom(Board::kPcfAddress,uint8_t(1))!=1)return false;
  const int b=Wire.read();if(b<0)return false;bits=uint8_t(b);return true;
}
static bool initBus() {
  if(!Wire.begin(Board::kSda,Board::kScl,Board::kI2cHz))return false;
  Wire.setTimeOut(Board::kWireTimeoutMs);
  Wire.beginTransmission(Board::kPcfAddress);Wire.write(uint8_t(0xFF));
  if(Wire.endTransmission()!=0)return false; // all PCF pins must stay released
  if(!readPcf(pcfBits))return false;
  return screen.begin();
}
static void recoverBus() {
  if(controller.active()||jogActive)return;
  Wire.end();pinMode(Board::kSda,INPUT_PULLUP);
  pinMode(Board::kScl,OUTPUT_OPEN_DRAIN);digitalWrite(Board::kScl,HIGH);
  for(uint8_t i=0;i<9;++i){digitalWrite(Board::kScl,LOW);delayMicroseconds(5);digitalWrite(Board::kScl,HIGH);delayMicroseconds(5);}
  pinMode(Board::kSda,OUTPUT_OPEN_DRAIN);digitalWrite(Board::kSda,LOW);delayMicroseconds(5);
  digitalWrite(Board::kScl,HIGH);delayMicroseconds(5);digitalWrite(Board::kSda,HIGH);
  ioHealthy=initBus()&&hardware.healthy();
  if(ioHealthy){buttons.reset(pcfBits,millis());logText("I2C RESTORED; RUN ACKNOWLEDGES FAULT, NO AUTOMATIC RESTART\n");}
}
static bool saveNow() {
  if(controller.active()||jogActive)return false;
  bool changed=controller.settingsChanged();pendingSave=pendingSave||changed;
  if(!pendingSave)return true;
  uint8_t data[dealer::kSettingsBytes];dealer::encodeSettings(controller.settings(),data);
  if(!nvsReady||preferences.putBytes("settings",data,sizeof(data))!=sizeof(data)) {
    editAt=millis();showNotice("儲存失敗");logText("NVS SAVE FAILED\n");return false;
  }
  pendingSave=false;return true;
}
static bool configure(const dealer::Settings& s) {
  if(jogActive||!controller.configure(s)){showNotice("超過設定範圍");return false;}
  pendingSave=true;editAt=millis();return true;
}
static void stopJog() {hardware.feed(0);hardware.eject(0);jogActive=false;}
static void acknowledgeFault() {
  if(controller.stage()!=dealer::Stage::Fault)return;
  controller.clearFault(millis());
  if(controller.stage()!=dealer::Stage::Idle)return;
  // A lost qualified edge must not leave the controller stuck in stale blockage.
  portENTER_CRITICAL(&edgeMux);
  edgeHead=0;edgeTail=0;edgeOverflow=false;
  const uint32_t at=micros();
  const bool blocked=hardware.outletRawBlocked();
  exitQualifier.reset(blocked,at);
  candidateLevel=blocked;candidatePosition=sampledCommandPosition;
  portEXIT_CRITICAL(&edgeMux);
  controller.resyncOutlet(blocked,at); // no counting; still wait 20ms before start
}
static void runAction() {
  const uint32_t ms=millis(),us=micros();
  if(jogActive){stopJog();return;}
  if(controller.stage()==dealer::Stage::Fault){acknowledgeFault();return;}
  if(controller.stage()==dealer::Stage::Calibrating){controller.abort(ms);return;}
  if(controller.stage()==dealer::Stage::Paused){controller.resume(ms,us);return;}
  if(controller.active()){controller.requestPause();return;}
  if(advanced) {
    if(advancedField==1){saveNow();advanced=false;recordedStart(true);}
    else{saveNow();advanced=false;}
    return;
  }
  saveNow();
  recordedStart(false);
  if(controller.error()==dealer::Error::NeedCalibration)showNotice("長按SET校正");
}
static void handleButton(const dealer::ButtonEvent& e) {
  using dealer::Button;using dealer::Press;
  if(e.button==Button::Run) {
    if(e.press==Press::Long){stopJog();controller.abort(millis());advanced=false;}
    else if(e.press==Press::Short)runAction();return;
  }
  if(controller.active()||controller.stage()==dealer::Stage::Fault||jogActive)return;
  if(e.button==Button::Set) {
    if(e.press==Press::Long){advanced=!advanced;advancedField=controller.settings().calibrated?0:1;if(!advanced)saveNow();}
    else if(e.press==Press::Short){if(advanced)advancedField=(advancedField+1)%DealerDisplay::kAdvancedFieldCount;else field=(field+1)%3;}
    return;
  }
  const int delta=e.button==Button::Plus?1:-1;
  dealer::Settings s=controller.settings();
  if(advanced) {
    switch(advancedField) {
      case 0:dealer::applyProfile(s,dealer::Profile((int(s.profile)+delta+5)%5));break;
      case 2:{int v=int(s.feedPwm)+delta*5;if(v<40||v>255)return;s.feedPwm=uint8_t(v);break;}
      case 3:{int v=int(s.ejectStartPwm)+delta*5;if(v<40||v>255)return;s.ejectStartPwm=uint8_t(v);break;}
      case 4:{
        const int current=s.ejectStartMs;
        const int step=dealer::kEjectStartStepMs;
        if((delta<0 && current==0) || (delta>0 && current==dealer::kMaxEjectStartMs))return;
        const int next=delta>0 ? (current/step+1)*step : ((current-1)/step)*step;
        s.ejectStartMs=uint16_t(next);
        break;
      }
      case 5:{int v=int(s.ejectPwm)+delta*5;if(v<40||v>255)return;s.ejectPwm=uint8_t(v);break;}
      case 6:{
        int v=int(s.reversePwm)+delta*5;
        if(s.reversePwm==0&&delta>0)v=40;
        if(s.reversePwm==40&&delta<0)v=0;
        if(v<0||v>255)return;
        s.reversePwm=uint8_t(v);break;
      }
      case 7:{int v=int(s.reverseMs)+delta*10;if(v<0||v>300)return;s.reverseMs=uint16_t(v);break;}
      case 8:{
        const uint16_t next=dealer::nextYawRate(s.maxStepRate,delta);
        if(next==s.maxStepRate)return;
        s.maxStepRate=next;break;
      }
      case 9:{
        int v=delta>0?(int(s.acceleration)/100+1)*100:(int(s.acceleration)-1)/100*100;
        if(v<100||v>dealer::kMaxYawAcceleration)return;
        s.acceleration=uint16_t(v);break;
      }
      case 10:s.continuousYaw=delta>0;break;
      case 11:{
        const int next=s.releaseTrimMs+delta*dealer::kTrimStepMs;
        if(next< -dealer::kMaxReleaseTrimMs||next>dealer::kMaxReleaseTrimMs)return;
        s.releaseTrimMs=int16_t(next);break;
      }
      case 12:s.counterclockwise=delta<0;break;
      default:return;
    }
  } else {
    if(field==0){int v=int(s.cards)+delta;if(v<1||v>36)return;s.cards=uint8_t(v);}
    if(field==1)s.players=s.players==3?4:3;
    if(field==2){int v=int(s.remainder)+delta;if(v<0||v>54)return;s.remainder=uint8_t(v);}
    s.profile=dealer::Profile::Custom;
  }
  configure(s);
}
static void logStatus() {
  char line[1280];const dealer::Settings& s=controller.settings();
  const auto& unexpected=controller.unexpectedExit();
  portENTER_CRITICAL(&edgeMux);
  const uint32_t rawEdges=exitRawCount,qualifiedEdges=exitQualifiedCount,overflows=exitOverflowCount;
  portEXIT_CRITICAL(&edgeMux);
  snprintf(line,sizeof(line),"{\"stage\":\"%s\",\"error\":\"%s\",\"fault_stage\":\"%s\",\"home_fault\":\"%s\",\"home_fault_pos\":%ld,\"home_fault_travel\":%ld,\"players\":%u,\"cards\":%u,\"rest\":%u,\"done\":%u,\"p\":[%u,%u,%u,%u],\"extra_done\":%u,\"calibrated\":%s,\"turn_fixed\":%s,\"turn_steps\":%.4f,\"position\":%ld,\"exit_blocked\":%s,\"home_blocked\":%s,\"pcf\":%u,\"feed_pwm\":%d,\"eject_pwm\":%u,\"feed_setting\":%u,\"eject_setting\":%u,\"eject_stage1\":%u,\"eject_stage2\":%u,\"eject_start_ms\":%u,\"reverse_pwm\":%u,\"reverse_ms\":%u,\"speed\":%u,\"speed_pct\":%.2f,\"speed_steps_s\":%u,\"acceleration\":%u,\"continuous\":%s,\"yaw_direction\":\"%s\",\"continuous_rate\":%u,\"release_trim_ms\":%d,\"sweeping\":%s,\"measured_release_ms\":%u,\"phase_error_steps\":%ld,\"exit_raw_edges\":%lu,\"exit_qualified_edges\":%lu,\"exit_overflows\":%lu,\"e06_count\":%lu,\"e06_last_stage\":\"%s\",\"wifi_off\":%s,\"ble_off\":%s}\n",
    dealer::stageName(controller.stage()),dealer::errorName(controller.error()),
    controller.stage()==dealer::Stage::Fault?dealer::stageName(controller.faultStage()):"",controller.homeFault().label(),
    long(controller.homeFault().position),long(controller.homeFault().travel),s.players,s.cards,s.remainder,controller.done(),
    controller.playerCount(0),controller.playerCount(1),controller.playerCount(2),controller.playerCount(3),controller.remainderDone(),
    s.calibrated?"true":"false",controller.turnIsFixed()?"true":"false",double(s.turnQ16)/65536.0,long(hardware.position()),controller.exitBlocked()?"true":"false",
    controller.homeBlocked()?"true":"false",pcfBits,hardware.feedPwm(),hardware.ejectPwm(),
    s.feedPwm,s.ejectPwm,s.ejectStartPwm,s.ejectPwm,s.ejectStartMs,s.reversePwm,s.reverseMs,s.maxStepRate,double(s.maxStepRate)/dealer::kYawRatePerPercent,s.maxStepRate,s.acceleration,
    s.continuousYaw?"true":"false",yawDirectionName(s),s.maxStepRate,int(s.releaseTrimMs),
    controller.sweeping()?"true":"false",controller.measuredReleaseMs(),long(controller.phaseErrorSteps()),
    (unsigned long)rawEdges,(unsigned long)qualifiedEdges,(unsigned long)overflows,
    (unsigned long)unexpected.count,unexpected.count?dealer::stageName(unexpected.lastStage):"",
    RadioPower::wifiOff()?"true":"false",RadioPower::bluetoothOff()?"true":"false");logText(line);
}
static bool integerArg(const char* s,long& v) {
  if(!s||!*s)return false;char* end=nullptr;v=strtol(s,&end,10);return end&&!*end;
}
static void command(char* line) {
  char* ctx=nullptr;char* verb=strtok_r(line," \t",&ctx);if(!verb)return;
  char* a=strtok_r(nullptr," \t",&ctx);char* b=strtok_r(nullptr," \t",&ctx);
  if(strtok_r(nullptr," \t",&ctx)){logText("ERROR EXTRA ARGUMENTS\n");return;}
  if(strcmp(verb,"log")==0){flightCommand(a,b);return;}
  if(strcmp(verb,"cal")==0){calibrationLogCommand(a,b);return;}
  if(strcmp(verb,"help")==0)logText("cal status | cal export [1..4] (independent calibration history)\n");
  if(strcmp(verb,"help")==0)logText("log status | log export [1..4] (1=newest)\n");
  if(strcmp(verb,"help")==0){logText("status | scan | preset landlord/guandan/four13/three13 | set cards/players/rest/feed/eject1/eject_start_ms/eject2/eject/reverse/reverse_ms/speed_pct/accel/continuous/release_trim_ms VALUE (speed_pct 1..100; speed/continuous_rate legacy halfsteps/s) | set yaw_direction cw/ccw | calibrate (diagnostic) | start | pause | resume | abort | ack | jog feed/eject +/-MILLISECONDS (max500)\n");return;}
  if(strcmp(verb,"status")==0){logStatus();return;}
  if(strcmp(verb,"abort")==0){stopJog();controller.abort(millis());return;}
  if(strcmp(verb,"ack")==0){acknowledgeFault();return;}
  if(strcmp(verb,"pause")==0){controller.requestPause();return;}
  if(strcmp(verb,"resume")==0){controller.resume(millis(),micros());return;}
  if(strcmp(verb,"start")==0){if(!controller.active()&&!jogActive){advanced=false;saveNow();recordedStart(false);}return;}
  if(strcmp(verb,"calibrate")==0){if(!controller.active()&&!jogActive){advanced=false;saveNow();recordedStart(true);}return;}
  if(controller.active()||jogActive){logText("ERROR BUSY\n");return;}
  if(strcmp(verb,"scan")==0) {
    // Probe only supported addresses, not all 127 addresses in one blocking loop.
    char msg[64];Wire.beginTransmission(Board::kPcfAddress);uint8_t p=Wire.endTransmission();
    Wire.beginTransmission(Board::kOledAddress);uint8_t o=Wire.endTransmission();
    snprintf(msg,sizeof(msg),"PCF 0x%02X=%u OLED 0x%02X=%u (0=ACK)\n",Board::kPcfAddress,p,Board::kOledAddress,o);logText(msg);return;
  }
  dealer::Settings s=controller.settings();
  if(strcmp(verb,"preset")==0&&a&&!b) {
    if(strcmp(a,"landlord")==0)dealer::applyProfile(s,dealer::Profile::Landlord);
    else if(strcmp(a,"guandan")==0)dealer::applyProfile(s,dealer::Profile::Guandan);
    else if(strcmp(a,"four13")==0)dealer::applyProfile(s,dealer::Profile::Four13);
    else if(strcmp(a,"three13")==0)dealer::applyProfile(s,dealer::Profile::Three13);
    else{logText("ERROR PRESET\n");return;}configure(s);return;
  }
  if(strcmp(verb,"set")==0&&a&&b) {
    long v=0;
    if(strcmp(a,"yaw_direction")==0) {
      if(strcmp(b,"cw")==0)s.counterclockwise=false;
      else if(strcmp(b,"ccw")==0)s.counterclockwise=true;
      else {logText("USE set yaw_direction cw|ccw\n");return;}
    } else if(strcmp(a,"steps")==0) {
      if(controller.turnIsFixed()){logText("ERROR TURN STEPS FIXED IN FIRMWARE\n");return;}
      char* end=nullptr;double d=strtod(b,&end);
      if(!end||*end||!(d>=6000&&d<=10000)){logText("ERROR STEPS RANGE\n");return;}
      s.turnQ16=uint32_t(d*65536.0+0.5);s.calibrated=true;
    } else {
      if(!integerArg(b,v)){logText("ERROR INTEGER\n");return;}
      if(strcmp(a,"cards")==0&&v>=1&&v<=36){s.cards=uint8_t(v);s.profile=dealer::Profile::Custom;}
      else if(strcmp(a,"players")==0&&(v==3||v==4)){s.players=uint8_t(v);s.profile=dealer::Profile::Custom;}
      else if(strcmp(a,"rest")==0&&v>=0&&v<=54){s.remainder=uint8_t(v);s.profile=dealer::Profile::Custom;}
      else if(strcmp(a,"feed")==0&&v>=40&&v<=255)s.feedPwm=uint8_t(v);
      else if(strcmp(a,"eject")==0&&v>=40&&v<=255)s.ejectPwm=uint8_t(v);
      else if(strcmp(a,"eject1")==0&&v>=40&&v<=255)s.ejectStartPwm=uint8_t(v);
      else if(strcmp(a,"eject_start_ms")==0&&v>=0&&v<=dealer::kMaxEjectStartMs)s.ejectStartMs=uint16_t(v);
      else if(strcmp(a,"eject2")==0&&v>=40&&v<=255)s.ejectPwm=uint8_t(v);
      else if(strcmp(a,"reverse")==0&&(v==0||(v>=40&&v<=255)))s.reversePwm=uint8_t(v);
      else if(strcmp(a,"reverse_ms")==0&&(v==0||(v>=10&&v<=300)))s.reverseMs=uint16_t(v);
      else if(strcmp(a,"speed_pct")==0&&v>=1&&v<=100)s.maxStepRate=uint16_t(v*dealer::kYawRatePerPercent);
      else if((strcmp(a,"speed")==0||strcmp(a,"continuous_rate")==0)&&v>=dealer::kMinYawRate&&v<=dealer::kMaxYawRate)s.maxStepRate=uint16_t(v);
      else if(strcmp(a,"accel")==0&&v>=100&&v<=dealer::kMaxYawAcceleration)s.acceleration=uint16_t(v);
      else if(strcmp(a,"continuous")==0&&(v==0||v==1))s.continuousYaw=(v==1);
      else if(strcmp(a,"release_trim_ms")==0&&v>=-dealer::kMaxReleaseTrimMs&&v<=dealer::kMaxReleaseTrimMs&&v%dealer::kTrimStepMs==0)s.releaseTrimMs=int16_t(v);
      else{logText("ERROR SET RANGE OR KEY\n");return;}
    }
    configure(s);return;
  }
  if(strcmp(verb,"jog")==0&&a&&b) {
    long t;if(controller.stage()==dealer::Stage::Fault||!ioHealthy||!integerArg(b,t)||t==0||t>500||t< -500||!controller.outletClear(micros())){logText("ERROR JOG CONDITION\n");return;}
    if(strcmp(a,"feed")==0)hardware.feed(t>0?s.feedPwm:-int(s.feedPwm));
    else if(strcmp(a,"eject")==0&&t>0)hardware.eject(s.ejectStartPwm);
    else{logText("ERROR JOG MOTOR\n");return;}
    jogDuration=uint32_t(t>0?t:-t);jogAt=millis();jogActive=true;logText("JOG: RELOAD/RECOUNT CARDS BEFORE A GAME\n");return;
  }
  logText("ERROR COMMAND; TYPE help\n");
}
static void pollConsole() {
  static char line[96];static size_t used=0;static bool dropping=false;
  for(uint8_t n=0;n<32&&Serial.available();++n) {
    char c=char(Serial.read());if(c=='\r')continue;
    if(c=='\n'){if(!dropping){line[used]=0;command(line);serviceFlight();}else logText("ERROR LINE TOO LONG\n");used=0;dropping=false;}
    else if(used<sizeof(line)-1&&!dropping)line[used++]=c;
    else dropping=true;
  }
}
void setup() {
  flight::mount();
  const bool motorsOk=hardware.init();
  const bool radiosOk=RadioPower::disable();
  pinMode(Board::kExitPin,INPUT); // mandatory external pull-up, no 5V on GPIO
  Serial.setTxTimeoutMs(0);Serial.begin(115200);
  dealer::Settings settings;nvsReady=preferences.begin("carddealer",false);
  if(nvsReady&&preferences.getBytesLength("settings")==dealer::kSettingsBytes) {
    uint8_t data[dealer::kSettingsBytes];
    if(preferences.getBytes("settings",data,sizeof(data))==sizeof(data))
      dealer::decodeSettings(data,sizeof(data),settings,&pendingSave);
  }
  ioHealthy=initBus()&&motorsOk;
  const bool exit=(digitalRead(Board::kExitPin)!=LOW)==Board::kExitBlockedHigh;
  const bool home=((pcfBits&(1U<<Board::kHomePcfBit))!=0)==Board::kHomeBlockedHigh;
  controller.begin(settings,exit,home,millis(),micros());buttons.reset(pcfBits,millis());
  portENTER_CRITICAL(&edgeMux);
  exitQualifier.reset(exit,micros());exitSamplingReady=true;
  candidateLevel=exit;candidatePosition=sampledCommandPosition;
  portEXIT_CRITICAL(&edgeMux);
  attachInterrupt(digitalPinToInterrupt(Board::kExitPin),exitInterrupt,CHANGE);
  // Reconcile a transition between the initial read and attaching CHANGE.
  portENTER_CRITICAL(&edgeMux);
  ExitEdge initialEvent;
  const uint32_t initialUs=micros();
  const bool initialLevel=(gpio_ll_get_level(&GPIO,Board::kExitPin)!=0)==Board::kExitBlockedHigh;
  if(exitQualifier.observe(initialLevel,initialUs,initialEvent))publishExit(initialEvent);
  candidateLevel=initialLevel;candidatePosition=sampledCommandPosition;
  portEXIT_CRITICAL(&edgeMux);
  logText("CARD DEALER V1.0.0 / CONTINUOUS YAW / RF TWO-STAGE ADJUSTABLE / EXIT REVERSE + QUALIFIER / HOME DIAG / FAST YAW / CAD V1.0.0 / C3 SUPERMINI / USB CDC\nType help. Aim whole unit at player 1 before dealing.\n");
  logText(radiosOk?"WIFI/BLE OFF; LOCAL CONTROLS ONLY\n":"WARNING: RADIO SHUTDOWN NOT CONFIRMED; CHECK status\n");
  enableLoopWDT();
}
void loop() {
  uint32_t ms=millis();
  const uint16_t yawRate=controller.settings().maxStepRate;
  const uint32_t pcfInterval=controller.sweeping() || controller.stage()==dealer::Stage::Positioning
    ? dealer::positioningPollMs(yawRate,Board::kPcfPollMs)
    : Board::kPcfPollMs;
  bool homeSampleFresh=false;
  if(ioHealthy&&uint32_t(ms-pcfAt)>=pcfInterval) {
    pcfAt=ms;
    homeSampleFresh=readPcf(pcfBits);
    if(!homeSampleFresh)ioHealthy=false;
  }
  // A dropped qualified edge makes the queued history untrustworthy.
  portENTER_CRITICAL(&edgeMux);
  bool overflow=edgeOverflow;edgeOverflow=false;
  if(overflow)edgeTail=edgeHead;
  portEXIT_CRITICAL(&edgeMux);
  ExitEdge event;
  int32_t edgeStep;
  if(!overflow)for(uint8_t n=0;n<kEdges&&popEdge(event,edgeStep);++n){
    const uint32_t nowMs=millis();
    const uint32_t eventMs=nowMs-uint32_t(micros()-event.us)/1000U;
    flightRecorder.edge(controller,event.blocked,event.us,eventMs,edgeStep);
    controller.qualifiedExitEdge(event.blocked,event.us,eventMs,edgeStep,nowMs);
    flightRecorder.stage(controller,nowMs);
  }
  portENTER_CRITICAL(&edgeMux);
  overflow=overflow||edgeOverflow;edgeOverflow=false;
  if(overflow)edgeTail=edgeHead;
  portEXIT_CRITICAL(&edgeMux);
  const dealer::Stage before=controller.stage();
  const bool home=((pcfBits&(1U<<Board::kHomePcfBit))!=0)==Board::kHomeBlockedHigh;
  controller.tick(millis(),micros(),home,ioHealthy&&hardware.healthy(),overflow,homeSampleFresh);
  serviceFlight();
  if(controller.stage()==dealer::Stage::Fault)jogActive=false;
  if(before==dealer::Stage::Calibrating&&controller.stage()==dealer::Stage::Idle) {
    if(saveNow())showNotice(calibrationRamOnly?"CAL RAM ONLY":"校正完成");
  }
  if(jogActive&&uint32_t(millis()-jogAt)>=jogDuration)stopJog();
  if(ioHealthy){dealer::ButtonEvent b;for(uint8_t i=0;i<4&&buttons.update(pcfBits,millis(),b);++i){handleButton(b);serviceFlight();}}
  pollConsole();hardware.service();
  if(controller.settingsChanged()){pendingSave=true;editAt=millis();}
  if(pendingSave&&!controller.active()&&!jogActive&&controller.stage()!=dealer::Stage::Fault&&uint32_t(millis()-editAt)>=2000)saveNow();
  if(notice&&uint32_t(millis()-noticeAt)>=2200)notice=nullptr;
  if(ioHealthy) {
    // OLED chunks share the 100kHz PCF bus. Reserve it for home and button
    // samples during the fastest moves; pending screen transfers resume at rest.
    const bool reserveBus=(controller.sweeping() || controller.stage()==dealer::Stage::Positioning) && yawRate>=dealer::kFastHomePollRate;
    if(!reserveBus){
      if(!screen.busy()&&uint32_t(millis()-drawAt)>=Board::kDisplayFrameMs){drawAt=millis();screen.compose(controller,field,advanced,advancedField,notice);}
      if(!screen.service()) {ioHealthy=false;controller.externalFault(dealer::Error::IoFault,millis());}
    }
  } else if(!controller.active()&&!jogActive&&uint32_t(millis()-recoveryAt)>=2000){recoveryAt=millis();recoverBus();}
  static dealer::Stage lastStage=dealer::Stage::Fault;static dealer::Error lastError=dealer::Error::Aborted;
  if(lastStage!=controller.stage()||lastError!=controller.error()){
    lastStage=controller.stage();lastError=controller.error();if(!exporting)logStatus();
  }
  serviceFlight();streamFlight();flushLog();delay(1);
}
