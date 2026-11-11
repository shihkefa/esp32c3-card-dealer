#include <Arduino.h>
#include <Wire.h>
#include <Preferences.h>
#include <esp_arduino_version.h>
#include <soc/gpio_struct.h>
#include <hal/gpio_ll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "BoardConfig.h"
#include "DealerCore.h"
#include "Display.h"
#include "EdgeEvent.h"
#include "RadioPower.h"
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
static portMUX_TYPE motionMux=portMUX_INITIALIZER_UNLOCKED;
static bool holdCoils=false;
static hw_timer_t* stepTimer=nullptr;
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
  if(motion.tick())outputPhase();
  portEXIT_CRITICAL_ISR(&motionMux);
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
  void hold(bool on) override {portENTER_CRITICAL(&motionMux);holdCoils=on;outputPhase();portEXIT_CRITICAL(&motionMux);}
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
static dealer::Controller controller(hardware);
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
static volatile uint8_t edgeHead=0,edgeTail=0;
static volatile bool edgeOverflow=false;
static portMUX_TYPE edgeMux=portMUX_INITIALIZER_UNLOCKED;
static void IRAM_ATTR exitInterrupt() {
  const uint32_t at=micros();
  const bool blocked=(gpio_ll_get_level(&GPIO,Board::kExitPin)!=0)==Board::kExitBlockedHigh;
  portENTER_CRITICAL_ISR(&edgeMux);
  const uint8_t next=uint8_t((edgeHead+1)%kEdges);
  if(next==edgeTail)edgeOverflow=true;
  else{edgeQueue[edgeHead].us=at;edgeQueue[edgeHead].blocked=blocked;edgeHead=next;}
  portEXIT_CRITICAL_ISR(&edgeMux);
}
static bool popEdge(ExitEdge& e) {
  portENTER_CRITICAL(&edgeMux);
  if(edgeTail==edgeHead){portEXIT_CRITICAL(&edgeMux);return false;}
  e.us=edgeQueue[edgeTail].us;e.blocked=edgeQueue[edgeTail].blocked;
  edgeTail=uint8_t((edgeTail+1)%kEdges);portEXIT_CRITICAL(&edgeMux);return true;
}

// USB logging is buffered and never waits for a USB host or TX buffer space.
static char txQueue[1536];static uint16_t txHead=0,txTail=0;
static void logText(const char* s) {
  while(*s){uint16_t next=(txHead+1)%sizeof(txQueue);if(next==txTail)return;txQueue[txHead]=*s++;txHead=next;}
}
static void flushLog() {
  if(!Serial){txTail=txHead;return;}
  int room=Serial.availableForWrite();if(room<=0)return;
  uint8_t tmp[48];size_t n=0;
  while(n<sizeof(tmp)&&n<size_t(room)&&txTail!=txHead){tmp[n++]=uint8_t(txQueue[txTail]);txTail=(txTail+1)%sizeof(txQueue);}
  if(n)Serial.write(tmp,n);
}
static void showNotice(const char* s) {notice=s;noticeAt=millis();}
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
static void runAction() {
  const uint32_t ms=millis(),us=micros();
  if(jogActive){stopJog();return;}
  if(controller.stage()==dealer::Stage::Fault){controller.clearFault(ms);return;}
  if(controller.stage()==dealer::Stage::Calibrating){controller.abort(ms);return;}
  if(controller.stage()==dealer::Stage::Paused){controller.resume(ms,us);return;}
  if(controller.active()){controller.requestPause();return;}
  if(advanced) {
    if(advancedField==1){saveNow();advanced=false;controller.calibrate(ms,us);}
    else{saveNow();advanced=false;}
    return;
  }
  saveNow();
  if(!controller.start(ms,us)&&controller.error()==dealer::Error::NeedCalibration)showNotice("長按SET校正");
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
    else if(e.press==Press::Short){if(advanced)advancedField=(advancedField+1)%6;else field=(field+1)%3;}
    return;
  }
  const int delta=e.button==Button::Plus?1:-1;
  dealer::Settings s=controller.settings();
  if(advanced) {
    switch(advancedField) {
      case 0:dealer::applyProfile(s,dealer::Profile((int(s.profile)+delta+5)%5));break;
      case 2:{int v=int(s.feedPwm)+delta*5;if(v<40||v>255)return;s.feedPwm=uint8_t(v);break;}
      case 3:{int v=int(s.ejectPwm)+delta*5;if(v<40||v>255)return;s.ejectPwm=uint8_t(v);break;}
      case 4:{int v=int(s.maxStepRate)+delta*50;if(v<150||v>800)return;s.maxStepRate=uint16_t(v);break;}
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
  char line[512];const dealer::Settings& s=controller.settings();
  snprintf(line,sizeof(line),"{\"stage\":\"%s\",\"error\":\"%s\",\"players\":%u,\"cards\":%u,\"rest\":%u,\"done\":%u,\"p\":[%u,%u,%u,%u],\"extra_done\":%u,\"calibrated\":%s,\"turn_steps\":%.4f,\"position\":%ld,\"exit_blocked\":%s,\"home_blocked\":%s,\"pcf\":%u,\"feed_pwm\":%d,\"eject_pwm\":%u,\"wifi_off\":%s,\"ble_off\":%s}\n",
    dealer::stageName(controller.stage()),dealer::errorName(controller.error()),s.players,s.cards,s.remainder,controller.done(),
    controller.playerCount(0),controller.playerCount(1),controller.playerCount(2),controller.playerCount(3),controller.remainderDone(),
    s.calibrated?"true":"false",double(s.turnQ16)/65536.0,long(hardware.position()),controller.exitBlocked()?"true":"false",
    controller.homeBlocked()?"true":"false",pcfBits,hardware.feedPwm(),hardware.ejectPwm(),
    RadioPower::wifiOff()?"true":"false",RadioPower::bluetoothOff()?"true":"false");logText(line);
}
static bool integerArg(const char* s,long& v) {
  if(!s||!*s)return false;char* end=nullptr;v=strtol(s,&end,10);return end&&!*end;
}
static void command(char* line) {
  char* ctx=nullptr;char* verb=strtok_r(line," \t",&ctx);if(!verb)return;
  char* a=strtok_r(nullptr," \t",&ctx);char* b=strtok_r(nullptr," \t",&ctx);
  if(strtok_r(nullptr," \t",&ctx)){logText("ERROR EXTRA ARGUMENTS\n");return;}
  if(strcmp(verb,"help")==0){logText("status | scan | preset landlord/guandan/four13/three13 | set cards/players/rest/feed/eject/speed/steps VALUE | calibrate | start | pause | resume | abort | ack | jog feed/eject +/-MILLISECONDS (max500)\n");return;}
  if(strcmp(verb,"status")==0){logStatus();return;}
  if(strcmp(verb,"abort")==0){stopJog();controller.abort(millis());return;}
  if(strcmp(verb,"ack")==0){controller.clearFault(millis());return;}
  if(strcmp(verb,"pause")==0){controller.requestPause();return;}
  if(strcmp(verb,"resume")==0){controller.resume(millis(),micros());return;}
  if(strcmp(verb,"start")==0){if(!controller.active()&&!jogActive){advanced=false;saveNow();controller.start(millis(),micros());}return;}
  if(strcmp(verb,"calibrate")==0){if(!controller.active()&&!jogActive){advanced=false;saveNow();controller.calibrate(millis(),micros());}return;}
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
    if(strcmp(a,"steps")==0) {
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
      else if(strcmp(a,"speed")==0&&v>=150&&v<=800)s.maxStepRate=uint16_t(v);
      else{logText("ERROR SET RANGE OR KEY\n");return;}
    }
    configure(s);return;
  }
  if(strcmp(verb,"jog")==0&&a&&b) {
    long t;if(controller.stage()==dealer::Stage::Fault||!ioHealthy||!integerArg(b,t)||t==0||t>500||t< -500||!controller.outletClear(micros())){logText("ERROR JOG CONDITION\n");return;}
    if(strcmp(a,"feed")==0)hardware.feed(t>0?s.feedPwm:-int(s.feedPwm));
    else if(strcmp(a,"eject")==0&&t>0)hardware.eject(s.ejectPwm);
    else{logText("ERROR JOG MOTOR\n");return;}
    jogDuration=uint32_t(t>0?t:-t);jogAt=millis();jogActive=true;logText("JOG: RELOAD/RECOUNT CARDS BEFORE A GAME\n");return;
  }
  logText("ERROR COMMAND; TYPE help\n");
}
static void pollConsole() {
  static char line[96];static size_t used=0;static bool dropping=false;
  for(uint8_t n=0;n<32&&Serial.available();++n) {
    char c=char(Serial.read());if(c=='\r')continue;
    if(c=='\n'){if(!dropping){line[used]=0;command(line);}else logText("ERROR LINE TOO LONG\n");used=0;dropping=false;}
    else if(used<sizeof(line)-1&&!dropping)line[used++]=c;
    else dropping=true;
  }
}
void setup() {
  const bool motorsOk=hardware.init();
  const bool radiosOk=RadioPower::disable();
  pinMode(Board::kExitPin,INPUT); // mandatory external pull-up, no 5V on GPIO
  Serial.setTxTimeoutMs(0);Serial.begin(115200);
  dealer::Settings settings;nvsReady=preferences.begin("carddealer",false);
  if(nvsReady&&preferences.getBytesLength("settings")==dealer::kSettingsBytes) {
    uint8_t data[dealer::kSettingsBytes];if(preferences.getBytes("settings",data,sizeof(data))==sizeof(data))dealer::decodeSettings(data,sizeof(data),settings);
  }
  ioHealthy=initBus()&&motorsOk;
  const bool exit=(digitalRead(Board::kExitPin)!=LOW)==Board::kExitBlockedHigh;
  const bool home=((pcfBits&(1U<<Board::kHomePcfBit))!=0)==Board::kHomeBlockedHigh;
  controller.begin(settings,exit,home,millis(),micros());buttons.reset(pcfBits,millis());
  attachInterrupt(digitalPinToInterrupt(Board::kExitPin),exitInterrupt,CHANGE);
  logText("CARD DEALER V1.0.0 / CAD V1.0.0 / C3 SUPERMINI / USB CDC\nType help. First use: empty hopper, calibrate, then aim whole unit at player 1.\n");
  logText(radiosOk?"WIFI/BLE OFF; LOCAL CONTROLS ONLY\n":"WARNING: RADIO SHUTDOWN NOT CONFIRMED; CHECK status\n");
  enableLoopWDT();
}
void loop() {
  uint32_t ms=millis();
  if(ioHealthy&&uint32_t(ms-pcfAt)>=Board::kPcfPollMs) {pcfAt=ms;if(!readPcf(pcfBits))ioHealthy=false;}
  ExitEdge event;for(uint8_t n=0;n<kEdges&&popEdge(event);++n)controller.rawExitEdge(event.blocked,event.us,millis());
  portENTER_CRITICAL(&edgeMux);bool overflow=edgeOverflow;edgeOverflow=false;portEXIT_CRITICAL(&edgeMux);
  const dealer::Stage before=controller.stage();
  const bool home=((pcfBits&(1U<<Board::kHomePcfBit))!=0)==Board::kHomeBlockedHigh;
  controller.tick(millis(),micros(),home,ioHealthy&&hardware.healthy(),overflow);
  if(controller.stage()==dealer::Stage::Fault)jogActive=false;
  if(before==dealer::Stage::Calibrating&&controller.stage()==dealer::Stage::Idle) {pendingSave=true;saveNow();showNotice("校正完成");}
  if(jogActive&&uint32_t(millis()-jogAt)>=jogDuration)stopJog();
  if(ioHealthy){dealer::ButtonEvent b;for(uint8_t i=0;i<4&&buttons.update(pcfBits,millis(),b);++i)handleButton(b);}
  pollConsole();hardware.service();
  if(controller.settingsChanged()){pendingSave=true;editAt=millis();}
  if(pendingSave&&!controller.active()&&!jogActive&&controller.stage()!=dealer::Stage::Fault&&uint32_t(millis()-editAt)>=2000)saveNow();
  if(notice&&uint32_t(millis()-noticeAt)>=2200)notice=nullptr;
  if(ioHealthy) {
    if(!screen.busy()&&uint32_t(millis()-drawAt)>=Board::kDisplayFrameMs){drawAt=millis();screen.compose(controller,field,advanced,advancedField,notice);}
    if(!screen.service()) {ioHealthy=false;controller.externalFault(dealer::Error::IoFault,millis());}
  } else if(!controller.active()&&!jogActive&&uint32_t(millis()-recoveryAt)>=2000){recoveryAt=millis();recoverBus();}
  static dealer::Stage lastStage=dealer::Stage::Fault;static dealer::Error lastError=dealer::Error::Aborted;
  if(lastStage!=controller.stage()||lastError!=controller.error()){lastStage=controller.stage();lastError=controller.error();logStatus();}
  flushLog();delay(1);
}
