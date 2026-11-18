#include "DealerCore.h"
#include "StepperPlan.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <climits>
using namespace dealer;
static unsigned checks=0,cases=0;
#define REQUIRE(x) do{++checks;if(!(x)){std::fprintf(stderr,"FAIL %s:%d %s\n",__FILE__,__LINE__,#x);std::exit(1);}}while(0)
struct FakeHardware:Hardware {
  StepperPlan plan;int32_t offset=0;int16_t feedValue=0;uint8_t ejectValue=0;bool holding=false,rawBlocked=false;
  std::vector<int32_t> targets;
  std::vector<int16_t> feedCommands;
  std::vector<uint8_t> ejectCommands;
  uint16_t commandedRate=0,commandedAccel=0;
  bool moveTo(int32_t target,uint16_t s,uint16_t a) override {
    targets.push_back(target);commandedRate=s;commandedAccel=a;
    return plan.start(target-offset,s,a);
  }
  int32_t position() const override{return offset+plan.position();}
  bool moving() const override{return plan.busy();}
  void setCounterclockwise(bool enabled) override{plan.setCounterclockwise(enabled);}
  void stopMotion() override{plan.stop();}
  void brakeMotion() override{plan.brake();}
  void hold(bool b) override{holding=b;}
  bool outletRawBlocked() const override{return rawBlocked;}
  void feed(int16_t v) override{feedValue=v;feedCommands.push_back(v);}
  void eject(uint8_t v) override{ejectValue=v;ejectCommands.push_back(v);}
};
struct Harness {
  FakeHardware hw;Controller c;uint64_t time=0;uint32_t physicalTurnQ16=kNominalTurnQ16;
  bool homeEnabled=true,homeStuck=false,homeSample=false;
  uint32_t homePollAt=0;bool rawExit=false;bool cardScheduled=false,cardBlocked=false;
  uint64_t cardStart=0;
  int32_t shaftTravel=0; // Reconstructed from coil phases; CW is positive.
  explicit Harness(Settings s=Settings{},int32_t offset=0,uint64_t initial=0,bool blocked=false,uint32_t fixedTurnQ16=0)
      :c(hw,fixedTurnQ16),time(initial),rawExit(blocked) {
    hw.offset=offset;c.begin(s,blocked,false,ms(),us());advance(30);
  }
  uint32_t ms() const{return uint32_t(time/1000);}
  uint32_t us() const{return uint32_t(time);}
  void edge(bool v,uint32_t stamp=0) {rawExit=v;hw.rawBlocked=v;c.rawExitEdge(v,stamp?stamp:us(),ms());}
  void oneMs(bool io=true,bool overflow=false) {
    for(int i=0;i<10;++i){
      const uint8_t prior=hw.plan.phase();
      if(hw.plan.tick())shaftTravel+=(hw.plan.phase()==((prior+1)&7))?1:-1;
      time+=100;
    }
    const uint16_t rate=c.settings().maxStepRate;
    const uint32_t referenceInterval=c.stage()==Stage::Positioning || c.sweeping()
      ? positioningPollMs(rate,5) : 5;
    const bool homeSampleFresh=uint32_t(ms()-homePollAt)>=referenceInterval;
    if(homeSampleFresh) {
      homePollAt=ms();
      const int64_t p=((int64_t(hw.offset)+shaftTravel-100)*65536)%physicalTurnQ16;
      const int64_t phase=p<0?p+physicalTurnQ16:p;
      homeSample=homeStuck||(homeEnabled&&phase<50*65536);
    }
    c.tick(ms(),us(),homeSample,io,overflow,homeSampleFresh);
  }
  void advance(unsigned n,bool io=true){for(unsigned i=0;i<n;++i)oneMs(io);}
  void wait(Stage s,unsigned maxMs=20000) {
    for(unsigned i=0;i<maxMs&&c.stage()!=s&&c.stage()!=Stage::Fault;++i)oneMs();
    REQUIRE(c.stage()==s);
  }
  void card() {
    wait(Stage::Feeding);edge(true);advance(3);REQUIRE(c.stage()==Stage::Exiting);
    REQUIRE(hw.feedValue==((c.settings().reversePwm&&c.settings().reverseMs)?-int(c.settings().reversePwm):0));
    advance(30);edge(false);advance(13);REQUIRE(c.stage()==Stage::Tail);
  }
  void autoStep() {
    if(c.stage()==Stage::Feeding&&!cardScheduled){cardScheduled=true;cardBlocked=false;cardStart=time;}
    if(cardScheduled&&!cardBlocked&&time-cardStart>=60000){edge(true);cardBlocked=true;}
    if(cardScheduled&&cardBlocked&&time-cardStart>=100000){edge(false);cardScheduled=false;}
    oneMs();
  }
  void finish(unsigned maxMs=1000000) {
    for(unsigned i=0;i<maxMs&&c.stage()!=Stage::Complete&&c.stage()!=Stage::Fault;++i)autoStep();
  }
};
static Settings calibrated(Profile p=Profile::Landlord) {Settings s;applyProfile(s,p);s.calibrated=true;return s;}
static void roundTest(Profile p) {
  ++cases;Settings s=calibrated(p);Harness h(s,12345);
  REQUIRE(h.c.start(h.ms(),h.us()));REQUIRE(h.hw.targets.front()==12345);
  h.finish();REQUIRE(h.c.stage()==Stage::Complete);REQUIRE(h.c.done()==totalCards(s));
  for(uint8_t i=0;i<s.players;++i)REQUIRE(h.c.playerCount(i)==s.cards);
  REQUIRE(h.c.remainderDone()==s.remainder);REQUIRE(h.hw.feedValue==0&&h.hw.ejectValue==0);
  REQUIRE(h.hw.targets.size()==totalCards(s));
  for(unsigned i=0;i<h.hw.targets.size();++i)REQUIRE(h.hw.targets[i]==plannedTarget(s,12345,uint16_t(i)));
  h.advance(1300);REQUIRE(!h.hw.holding);
}
static void settingsTests() {
  ++cases;Settings s=calibrated(Profile::Three13);uint8_t data[kSettingsBytes];encodeSettings(s,data);
  Settings out;REQUIRE(decodeSettings(data,sizeof(data),out));REQUIRE(out.players==3&&out.cards==13&&out.remainder==13&&out.calibrated);
  for(size_t i=0;i<sizeof(data);++i){data[i]^=1;REQUIRE(!decodeSettings(data,sizeof(data),out));data[i]^=1;}
  REQUIRE(!decodeSettings(data,sizeof(data)-1,out));s.players=4;s.cards=28;s.remainder=0;REQUIRE(!validSettings(s));
  Harness h;REQUIRE(!h.c.start(h.ms(),h.us()));REQUIRE(h.c.error()==Error::NeedCalibration);REQUIRE(h.hw.targets.empty());
  s=calibrated();s.cards=36;s.remainder=1;REQUIRE(!h.c.configure(s));
}
static void exactAngleTests() {
  ++cases;Settings s=calibrated(Profile::Landlord);s.turnQ16=8152UL*65536UL+16384;
  for(unsigned i=0;i<51;++i){int32_t actual=plannedTarget(s,0,uint16_t(i));double want=double(i)*8152.25/3;REQUIRE(double(actual)-want<0.501&&double(actual)-want> -0.501);}
  REQUIRE(plannedTarget(s,0,51)==int32_t(17*8152.25+8152.25/6+0.5));
  s=calibrated(Profile::Four13);s.remainder=3;
  REQUIRE(plannedTarget(s,0,52)==13*8192+1024);REQUIRE(plannedTarget(s,0,53)==plannedTarget(s,0,52));
  REQUIRE(plannedTarget(s,INT32_MAX-10,52)==INT32_MIN);
}
static void pauseAbortTests() {
  ++cases;Harness h(calibrated());REQUIRE(h.c.start(h.ms(),h.us()));h.wait(Stage::Feeding);
  h.c.requestPause();h.card();REQUIRE(h.c.done()==1);h.advance(70);
  REQUIRE(h.c.stage()==Stage::Paused);REQUIRE(h.hw.feedValue==0&&h.hw.ejectValue==0&&h.hw.holding);
  h.advance(5000);REQUIRE(h.c.done()==1);REQUIRE(h.c.resume(h.ms(),h.us()));
  h.wait(Stage::Positioning);h.advance(200);REQUIRE(h.hw.moving());h.c.abort(h.ms());
  REQUIRE(h.c.stage()==Stage::Fault&&h.c.error()==Error::Aborted);REQUIRE(!h.hw.moving()&&!h.hw.holding);
  REQUIRE(h.hw.feedValue==0&&h.hw.ejectValue==0);REQUIRE(!h.c.resume(h.ms(),h.us()));
  h.oneMs();h.c.clearFault(h.ms());REQUIRE(h.c.done()==0&&h.c.playerCount(0)==0&&h.c.stage()==Stage::Idle);
}
static void pauseBeforeFeedTest() {
  ++cases;Harness h(calibrated());REQUIRE(h.c.start(h.ms(),h.us()));h.wait(Stage::SpinUp);
  h.c.requestPause();h.oneMs();REQUIRE(h.c.stage()==Stage::Paused&&h.c.done()==0);
  REQUIRE(h.hw.feedValue==0&&h.hw.ejectValue==0);REQUIRE(h.c.resume(h.ms(),h.us()));h.card();REQUIRE(h.c.done()==1);
}
static void jamTests() {
  ++cases;Harness h(calibrated());h.c.start(h.ms(),h.us());h.wait(Stage::Feeding);h.advance(1201);
  REQUIRE(h.c.error()==Error::NoCard&&h.c.done()==0);REQUIRE(h.hw.feedValue==0&&h.hw.ejectValue==0);
  Harness s(calibrated());s.c.start(s.ms(),s.us());s.wait(Stage::Feeding);s.edge(true);s.advance(3);s.advance(1401);
  REQUIRE(s.c.error()==Error::CardStuck&&s.c.done()==0);REQUIRE(s.hw.feedValue==0&&s.hw.ejectValue==0);
  Harness b(calibrated(),0,0,true);REQUIRE(!b.c.start(b.ms(),b.us()));REQUIRE(b.c.error()==Error::OutletBlocked);
}
static void sensorTests() {
  ++cases;Harness h(calibrated());h.c.start(h.ms(),h.us());h.wait(Stage::Feeding);
  const uint32_t first=h.us();h.c.rawExitEdge(true,first+100,h.ms());h.c.rawExitEdge(false,first+500,h.ms());h.advance(4);
  REQUIRE(h.c.stage()==Stage::Feeding&&h.c.done()==0);
  // A whole 8ms pulse arrives while loop() was occupied; original edge times
  // still yield exactly one count when the backlog is drained.
  const uint32_t at=h.us();h.time+=20000;
  h.c.rawExitEdge(true,at+2000,h.ms());h.c.rawExitEdge(false,at+10000,h.ms());h.advance(3);
  REQUIRE(h.c.done()==1&&h.c.stage()==Stage::Tail);
  h.edge(true);h.advance(3);REQUIRE(h.c.error()==Error::None&&h.c.done()==1);
  REQUIRE(h.c.unexpectedExit().count==1 && h.c.unexpectedExit().lastStage==Stage::Tail);
  h.edge(false);h.advance(15);REQUIRE(h.c.done()==1);h.card();REQUIRE(h.c.done()==2);
  Harness y(calibrated());y.c.start(y.ms(),y.us());y.card();y.advance(65);REQUIRE(y.c.stage()==Stage::Positioning);
  y.edge(true);y.advance(3);REQUIRE(y.c.error()==Error::None&&y.hw.moving());
  REQUIRE(y.c.unexpectedExit().count==1 && y.c.unexpectedExit().lastStage==Stage::Positioning);
  y.wait(Stage::Fault);REQUIRE(y.c.error()==Error::OutletBlocked && y.c.done()==1);
}
static void communicationTests() {
  ++cases;Harness h(calibrated());h.c.start(h.ms(),h.us());h.wait(Stage::Feeding);h.oneMs(false);
  REQUIRE(h.c.error()==Error::IoFault&&h.hw.feedValue==0&&h.hw.ejectValue==0);
  h.advance(100);REQUIRE(h.c.stage()==Stage::Fault);h.c.clearFault(h.ms());REQUIRE(h.c.stage()==Stage::Idle);
  Harness o(calibrated());o.c.start(o.ms(),o.us());o.oneMs(true,true);REQUIRE(o.c.error()==Error::SensorOverflow&&!o.hw.holding);
}
static void referenceTests() {
  ++cases;Harness missing(calibrated());missing.homeEnabled=false;missing.c.start(missing.ms(),missing.us());missing.finish();
  REQUIRE(missing.c.error()==Error::HomeMissing&&missing.c.done()<54);
  const auto miss=missing.c.homeFault();
  REQUIRE(miss.cause==HomeFault::Missing && std::strcmp(miss.label(),"MISS")==0);
  REQUIRE(miss.travel>8192*6/5 && miss.position==miss.travel);
  REQUIRE(missing.hw.feedValue==0 && missing.hw.ejectValue==0 && !missing.hw.moving() && !missing.hw.holding);
  Harness stuck(calibrated());stuck.homeStuck=true;stuck.advance(10);stuck.c.start(stuck.ms(),stuck.us());stuck.finish();
  REQUIRE(stuck.c.error()==Error::HomeMissing);
  const auto blocked=stuck.c.homeFault();
  REQUIRE(blocked.cause==HomeFault::Blocked && std::strcmp(blocked.label(),"BLOCKED")==0);
  REQUIRE(blocked.travel>8192/8 && blocked.travel<8192*6/5 && blocked.travel==blocked.position);
  // A later button abort, live input change, or bus fault must not erase E07.
  stuck.homeStuck=false;stuck.advance(5);stuck.c.abort(stuck.ms());stuck.oneMs(false);
  stuck.c.clearFault(stuck.ms());
  REQUIRE(stuck.c.error()==Error::HomeMissing && stuck.c.homeFault().position==blocked.position);
  REQUIRE(stuck.c.homeFault().cause==HomeFault::Blocked && !stuck.c.resume(stuck.ms(),stuck.us()));
  stuck.oneMs();stuck.c.clearFault(stuck.ms());stuck.advance(250);
  REQUIRE(stuck.c.stage()==Stage::Idle && stuck.c.done()==0 && stuck.c.homeFault().cause==HomeFault::None);
  REQUIRE(stuck.c.homeFault().travel==0 && stuck.c.homeFault().position==0 && !stuck.hw.moving());
  REQUIRE(stuck.hw.feedValue==0 && stuck.hw.ejectValue==0 && !stuck.hw.holding);
  Harness wrong(calibrated());wrong.physicalTurnQ16=8500UL*65536;wrong.c.start(wrong.ms(),wrong.us());wrong.finish();
  REQUIRE(wrong.c.error()==Error::HomeMismatch);
  ++cases;
  // A turn can start paused inside the reference slot. Time at rest must not
  // count toward the stuck-beam distance, nor synthesize a reference edge.
  Settings s=calibrated();s.cards=3;s.remainder=0;
  Harness parked(s,100);REQUIRE(parked.c.homeBlocked());REQUIRE(parked.c.start(parked.ms(),parked.us()));
  parked.c.requestPause();parked.wait(Stage::Paused);parked.advance(15000);
  REQUIRE(parked.c.stage()==Stage::Paused && parked.c.homeBlocked() && parked.hw.position()==100);
  REQUIRE(parked.c.homeFault().cause==HomeFault::None && parked.c.resume(parked.ms(),parked.us()));
  parked.finish();REQUIRE(parked.c.stage()==Stage::Complete && parked.c.done()==9);
}
static void calibrationTests() {
  ++cases;Harness h;h.physicalTurnQ16=8152UL*65536+16384;
  REQUIRE(h.c.calibrate(h.ms(),h.us()));REQUIRE(h.hw.feedValue==0&&h.hw.ejectValue==0);
  for(unsigned i=0;i<200000&&h.c.stage()==Stage::Calibrating;++i)h.oneMs();
  REQUIRE(h.c.stage()==Stage::Idle&&h.c.settings().calibrated);REQUIRE(h.c.calibrationTurns()==4);
  double measured=double(h.c.settings().turnQ16)/65536;REQUIRE(measured>8151.25&&measured<8153.25);
  REQUIRE(h.c.settingsChanged());REQUIRE(!h.c.settingsChanged());
  Harness no;no.homeEnabled=false;no.c.calibrate(no.ms(),no.us());
  for(unsigned i=0;i<50000&&no.c.stage()==Stage::Calibrating;++i)no.oneMs();
  REQUIRE(no.c.error()==Error::CalibrationFailed);
}

// Advance the PCF input and the commanded position independently so the first
// observation is distinguishable from the later debounce-confirming sample.
static void calibrationReading(Harness& h,bool level,int32_t position,uint32_t deltaMs,bool fresh=true) {
  h.time+=uint64_t(deltaMs)*1000;
  h.hw.offset=position;
  h.c.tick(h.ms(),h.us(),level,true,false,fresh);
}
static uint32_t calibrationCrossing(Harness& h,int32_t position) {
  calibrationReading(h,true,position-2,19990,false); // cached values do not start a sample
  calibrationReading(h,true,position,5);
  const uint32_t firstMs=h.ms();
  calibrationReading(h,true,position+1,5);
  calibrationReading(h,false,position+20,50);
  calibrationReading(h,false,position+22,5);
  return firstMs;
}

static void fixedTurnTests(uint32_t fixed) {
  ++cases;
  Harness fresh(Settings{},0,0,false,fixed);
  REQUIRE(fresh.c.turnIsFixed() && fresh.c.settings().calibrated && fresh.c.settings().turnQ16==fixed);
  REQUIRE(fresh.c.start(fresh.ms(),fresh.us()));

  ++cases;
  Settings legacy=calibrated(Profile::Four13);
  legacy.turnQ16=7700UL*65536;
  legacy.feedPwm=215;legacy.maxStepRate=900;
  uint8_t bytes[kSettingsBytes];encodeSettings(legacy,bytes);
  Settings fromNvs;REQUIRE(decodeSettings(bytes,sizeof(bytes),fromNvs));
  Harness restored(fromNvs,0,0,false,fixed);
  REQUIRE(restored.c.settings().turnQ16==fixed && restored.c.settings().feedPwm==215);
  REQUIRE(restored.c.settings().maxStepRate==900 && restored.c.settings().profile==Profile::Four13);
  fromNvs.calibrated=false;fromNvs.turnQ16=9000UL*65536;
  fromNvs.feedPwm=220;
  REQUIRE(restored.c.configure(fromNvs));
  REQUIRE(restored.c.settings().turnQ16==fixed && restored.c.settings().calibrated && restored.c.settings().feedPwm==220);
  REQUIRE(restored.c.settingsChanged());
  REQUIRE(restored.c.calibrate(restored.ms(),restored.us()));
  for(int32_t p:{10,7710,15410,23110,30810})calibrationCrossing(restored,p);
  REQUIRE(restored.c.stage()==Stage::Idle && restored.c.calibrationTrace().count==5);
  REQUIRE(restored.c.calibrationTrace().completeMeanQ16()==7700UL*65536 && restored.c.calibrationTurns()==4);
  REQUIRE(restored.c.settings().turnQ16==fixed && !restored.c.settingsChanged());

  ++cases;
  Settings game=calibrated(Profile::Four13);game.cards=3;game.remainder=2;
  game.maxStepRate=1200;game.acceleration=800;
  Harness mismatched(game,0,0,false,fixed);
  mismatched.physicalTurnQ16=fixed+60UL*65536;
  REQUIRE(mismatched.c.start(mismatched.ms(),mismatched.us()));
  mismatched.finish();
  REQUIRE(mismatched.c.error()==Error::None && mismatched.c.done()==14);
  REQUIRE(mismatched.hw.targets.size()==14);
  for(unsigned i=0;i<14;++i) {
    const double turns=i<12?i/4.0:3.125;
    REQUIRE(mismatched.hw.targets[i]==int32_t(turns*fixed/65536.0+0.5));
  }
  for(unsigned player=0;player<4;++player)REQUIRE(mismatched.c.playerCount(player)==3);

  ++cases;
  Harness lost(game,0,0,false,fixed);lost.homeEnabled=false;
  REQUIRE(lost.c.start(lost.ms(),lost.us()));lost.finish();
  REQUIRE(lost.c.error()==Error::HomeMissing && lost.c.homeFault().cause==HomeFault::Missing);
  std::printf("FIXED_TURN q16=%lu\n",static_cast<unsigned long>(fixed));
}

static void calibrationTraceTests() {
  ++cases;
  Harness good(calibrated(),0,(uint64_t(UINT32_MAX)-30000)*1000);
  REQUIRE(good.c.calibrate(good.ms(),good.us()));
  const int32_t positions[]={100,8250,16402,24553,32705};
  uint32_t previous=0;
  for (uint8_t i=0;i<kCalibrationSamples;++i) {
    const uint32_t first=calibrationCrossing(good,positions[i]);
    const auto& trace=good.c.calibrationTrace();
    REQUIRE(trace.count==i+1 && trace.samples[i].position==positions[i] && trace.samples[i].ms==first);
    if (i) REQUIRE(uint32_t(first-previous)==20055);
    if (i==1) REQUIRE(first<previous); // real millis() wrap between crossings
    previous=first;
  }
  REQUIRE(good.c.stage()==Stage::Idle && good.c.calibrationTurns()==4);
  REQUIRE(good.c.settings().turnQ16==uint32_t(int64_t(positions[4]-positions[0])*65536/4));
  REQUIRE(good.c.start(good.ms(),good.us()));
  REQUIRE(good.c.calibrationTrace().count==0 && good.c.calibrationTurns()==0);

  ++cases;
  Harness invalid(calibrated());
  const uint32_t original=invalid.c.settings().turnQ16;
  REQUIRE(invalid.c.calibrate(invalid.ms(),invalid.us()));
  calibrationCrossing(invalid,100);calibrationCrossing(invalid,8251);
  const uint32_t rejectedAt=calibrationCrossing(invalid,13500);
  REQUIRE(invalid.c.error()==Error::CalibrationFailed && invalid.c.calibrationTurns()==1);
  REQUIRE(invalid.c.calibrationTrace().count==3 && invalid.c.calibrationTrace().samples[2].position==13500);
  REQUIRE(invalid.c.calibrationTrace().samples[2].ms==rejectedAt && invalid.c.settings().turnQ16==original);
  invalid.c.clearFault(invalid.ms());
  REQUIRE(invalid.c.calibrationTrace().count==3);
  invalid.hw.rawBlocked=true;
  REQUIRE(!invalid.c.calibrate(invalid.ms(),invalid.us()) && invalid.c.calibrationTrace().count==0);

  ++cases;
  Harness spread;
  REQUIRE(spread.c.calibrate(spread.ms(),spread.us()));
  for (int32_t position:{100,8200,16301,24402,32532}) calibrationCrossing(spread,position);
  REQUIRE(spread.c.error()==Error::CalibrationFailed && spread.c.calibrationTrace().count==5);
  REQUIRE(spread.c.calibrationTrace().samples[4].position==32532 && !spread.c.settings().calibrated);

  ++cases;
  Harness aborted;
  // A raw high already observed before calibration did not originate inside this run.
  calibrationReading(aborted,true,50,1);
  REQUIRE(aborted.c.calibrate(aborted.ms(),aborted.us()));
  calibrationReading(aborted,true,51,5);
  REQUIRE(aborted.c.calibrationTrace().count==0);
  calibrationReading(aborted,false,70,5);calibrationReading(aborted,false,72,5);
  calibrationCrossing(aborted,8200);
  aborted.c.abort(aborted.ms());
  REQUIRE(aborted.c.error()==Error::Aborted && aborted.c.calibrationTrace().count==1);
  REQUIRE(aborted.c.calibrationTrace().samples[0].position==8200);
  aborted.c.clearFault(aborted.ms());
  REQUIRE(aborted.c.calibrationTrace().count==1);
  REQUIRE(aborted.c.calibrate(aborted.ms(),aborted.us()) && aborted.c.calibrationTrace().count==0);
}
static void wrapTests() {
  ++cases;Harness h(calibrated(Profile::Four13),0,(uint64_t(UINT32_MAX)-500)*1000);
  REQUIRE(h.c.start(h.ms(),h.us()));h.finish();REQUIRE(h.c.stage()==Stage::Complete&&h.c.done()==52);
}
static void buttonTests() {
  ++cases;Buttons b;b.reset(0xFF,0);ButtonEvent e;
  REQUIRE(!b.update(0xFE,1,e));REQUIRE(!b.update(0xFF,10,e));REQUIRE(!b.update(0xFE,20,e));
  REQUIRE(!b.update(0xFE,51,e));REQUIRE(b.update(0xFE,1051,e)&&e.button==Button::Set&&e.press==Press::Long);
  REQUIRE(!b.update(0xFF,1060,e));REQUIRE(!b.update(0xFF,1091,e));
  b.reset(0xFF,0);REQUIRE(!b.update(0xFB,10,e));REQUIRE(!b.update(0xFB,41,e));
  REQUIRE(b.update(0xFB,550,e)&&e.press==Press::Repeat);REQUIRE(!b.update(0xFF,600,e));REQUIRE(!b.update(0xFF,631,e));
  b.reset(0xFF,0);b.update(0xF7,10,e);b.update(0xF7,41,e);REQUIRE(b.update(0xF7,1541,e)&&e.press==Press::Long);
  REQUIRE(!b.update(0xFF,1550,e));REQUIRE(!b.update(0xFF,1581,e));
}
static void stepperTests() {
  ++cases;StepperPlan p;REQUIRE(p.start(2000,600,300));REQUIRE(!p.start(10,600,300));
  unsigned steps=0;
  for(unsigned i=0;i<200000&&p.busy();++i)if(p.tick())++steps;
  REQUIRE(!p.busy()&&p.position()==2000&&steps==2000&&p.phase()==(2000&7));
  REQUIRE(p.start(-100,300,200));for(unsigned i=0;i<300000&&p.busy();++i)p.tick();REQUIRE(p.position()== -100);
  REQUIRE(!p.start(2000000,600,300));REQUIRE(p.start(100,600,300));
  for(unsigned i=0;i<3000;++i)p.tick();p.stop();int32_t last=p.position();for(int i=0;i<1000;++i)p.tick();REQUIRE(p.position()==last&&!p.busy());
}
static void reverseTests() {
  ++cases;
  Harness h(calibrated());REQUIRE(h.c.start(h.ms(),h.us()));h.wait(Stage::Feeding);
  h.edge(true);h.advance(1);REQUIRE(h.hw.feedValue==175);
  h.advance(2);REQUIRE(h.c.stage()==Stage::Exiting&&h.hw.feedValue==-175);
  REQUIRE(h.hw.ejectValue==200&&!h.hw.moving()&&h.c.done()==0);
  h.advance(15);h.edge(false);h.advance(13);
  REQUIRE(h.c.done()==1&&h.hw.feedValue==0&&h.c.stage()==Stage::Tail);
  unsigned negatives=0;for(int v:h.hw.feedCommands)if(v<0)++negatives;REQUIRE(negatives==1);

  ++cases;
  Harness timeout(calibrated());timeout.c.start(timeout.ms(),timeout.us());timeout.wait(Stage::Feeding);
  timeout.edge(true);timeout.advance(3);timeout.advance(50);
  REQUIRE(timeout.c.stage()==Stage::Exiting&&timeout.hw.feedValue==0&&timeout.hw.ejectValue==200);
  timeout.advance(100);unsigned before=unsigned(timeout.hw.feedCommands.size());timeout.advance(100);
  REQUIRE(timeout.hw.feedCommands.size()==before&&timeout.c.done()==0);
  timeout.advance(1200);REQUIRE(timeout.c.error()==Error::CardStuck&&timeout.hw.ejectValue==0);

  ++cases;
  for(unsigned mode=0;mode<2;++mode){
    Settings s=calibrated();if(mode==0)s.reversePwm=0;else s.reverseMs=0;
    Harness off(s);off.c.start(off.ms(),off.us());off.card();
    for(int v:off.hw.feedCommands)REQUIRE(v>=0);
  }

  ++cases;
  for(unsigned mode=0;mode<3;++mode){
    Harness stop(calibrated());stop.c.start(stop.ms(),stop.us());stop.wait(Stage::Feeding);
    stop.edge(true);stop.advance(3);REQUIRE(stop.hw.feedValue<0);
    if(mode==0)stop.c.abort(stop.ms());
    else if(mode==1)stop.oneMs(false);
    else stop.oneMs(true,true);
    REQUIRE(stop.hw.feedValue==0&&stop.hw.ejectValue==0&&stop.c.stage()==Stage::Fault);
    stop.advance(100);REQUIRE(stop.hw.feedValue==0);
  }

  ++cases;
  Harness pause(calibrated());pause.c.start(pause.ms(),pause.us());pause.wait(Stage::Feeding);
  pause.edge(true);pause.advance(3);pause.c.requestPause();pause.advance(10);
  REQUIRE(pause.c.stage()==Stage::Exiting&&pause.hw.feedValue<0);
  pause.edge(false);pause.advance(75);
  REQUIRE(pause.c.stage()==Stage::Paused&&pause.c.done()==1&&pause.hw.feedValue==0&&pause.hw.ejectValue==0);

  ++cases;
  Harness wrap(calibrated(),0,(uint64_t(UINT32_MAX)-220)*1000);
  wrap.c.start(wrap.ms(),wrap.us());wrap.wait(Stage::Feeding);wrap.edge(true);wrap.advance(3);
  REQUIRE(wrap.hw.feedValue<0);wrap.advance(55);REQUIRE(wrap.hw.feedValue==0&&wrap.c.stage()==Stage::Exiting);
}
static void migrationAndSpeedTests() {
  ++cases;
  const uint8_t old[]={0x43,0x44,0x52,0x31,0x04,0x0d,0x00,0x02,0xd2,0xe1,0x01,0x00,0x5e,0x01,0xfa,0x00,0x00,0x40,0xd8,0x1f,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xba,0x9f,0xc7,0xb2};
  Settings s;REQUIRE(decodeSettings(old,sizeof(old),s));
  REQUIRE(s.players==4&&s.cards==13&&s.remainder==0&&s.profile==Profile::Four13);
  REQUIRE(s.feedPwm==210&&s.ejectPwm==225&&s.ejectStartPwm==255&&s.calibrated&&s.turnQ16==534265856UL);
  REQUIRE(s.maxStepRate==350&&s.acceleration==250&&s.reversePwm==175&&s.reverseMs==50);
  REQUIRE(s.ejectStartMs==100);
  s.reversePwm=95;s.reverseMs=110;s.maxStepRate=1200;s.acceleration=1000;s.ejectStartPwm=245;
  uint8_t data[kSettingsBytes];encodeSettings(s,data);Settings out;
  REQUIRE(memcmp(data,"CDR8",4)==0&&decodeSettings(data,sizeof(data),out));
  REQUIRE(out.reversePwm==95&&out.reverseMs==110&&out.maxStepRate==1200&&out.acceleration==1000);
  REQUIRE(out.ejectStartPwm==245&&out.ejectPwm==225);
  s.reversePwm=39;REQUIRE(!validSettings(s));s.reversePwm=0;s.reverseMs=301;REQUIRE(!validSettings(s));
  s.reverseMs=9;REQUIRE(!validSettings(s));s.reverseMs=0;s.maxStepRate=kMaxYawRate+1;REQUIRE(!validSettings(s));
  s.maxStepRate=1200;REQUIRE(validSettings(s));
  ++cases;Harness fast(s);fast.physicalTurnQ16=s.turnQ16;
  REQUIRE(fast.c.start(fast.ms(),fast.us()));fast.finish();
  REQUIRE(fast.c.stage()==Stage::Complete&&fast.c.done()==52);
  ++cases;Harness guard(calibrated());guard.hw.rawBlocked=true;
  REQUIRE(!guard.c.start(guard.ms(),guard.us())&&guard.c.error()==Error::OutletBlocked);
  REQUIRE(guard.hw.feedValue==0&&guard.hw.ejectValue==0&&guard.hw.targets.empty());
  ++cases;Harness recovery(calibrated());recovery.c.start(recovery.ms(),recovery.us());
  recovery.wait(Stage::Feeding);recovery.edge(true);recovery.advance(3);
  recovery.oneMs(true,true);recovery.hw.rawBlocked=false;
  recovery.c.clearFault(recovery.ms());REQUIRE(recovery.c.exitBlocked());
  REQUIRE(recovery.c.resyncOutlet(false,recovery.us()));
  REQUIRE(!recovery.c.outletClear(recovery.us()));
  recovery.advance(21);REQUIRE(recovery.c.outletClear(recovery.us()));
  REQUIRE(recovery.c.start(recovery.ms(),recovery.us()));REQUIRE(!recovery.c.resyncOutlet(false,recovery.us()));
}
static uint32_t measuredMoveTicks(int32_t distance,uint16_t speed,uint16_t acceleration,uint32_t* peakRate=nullptr) {
  StepperPlan plan;REQUIRE(plan.start(distance,speed,acceleration));
  uint32_t ticks=0,steps=0;
  if(peakRate)*peakRate=0;
  while(plan.busy()&&ticks<2000000){
    if(plan.tick())++steps;
    if(peakRate&&plan.plannedMilliStepsPerSecond()>*peakRate)*peakRate=plan.plannedMilliStepsPerSecond();
    ++ticks;
  }
  REQUIRE(!plan.busy()&&plan.position()==distance&&steps==uint32_t(distance));
  REQUIRE(plan.phase()==uint8_t(distance&7));
  return ticks;
}
static void fasterYawTests() {
  ++cases;
  const uint8_t old3[]={0x43,0x44,0x52,0x33,0x04,0x0d,0x00,0x02,0xd2,0xe1,0x01,0x00,0x58,0x02,0x2c,0x01,0x00,0x40,0xd8,0x1f,0x5f,0xf5,0x6e,0x00,0x00,0x00,0x00,0x00,0x08,0x96,0xdf,0x69};
  Settings migrated;
  bool rewrite=false;
  REQUIRE(decodeSettings(old3,sizeof(old3),migrated,&rewrite)&&rewrite);
  REQUIRE(Settings{}.maxStepRate==600&&Settings{}.acceleration==300);
  REQUIRE(migrated.maxStepRate==600&&migrated.acceleration==300);
  REQUIRE(migrated.calibrated&&migrated.turnQ16==534265856UL&&migrated.players==4&&migrated.cards==13);
  REQUIRE(migrated.feedPwm==210&&migrated.ejectStartPwm==245&&migrated.ejectPwm==225);
  REQUIRE(migrated.reversePwm==95&&migrated.reverseMs==110);
  REQUIRE(migrated.ejectStartMs==100);
  const uint8_t custom3[]={0x43,0x44,0x52,0x33,0x04,0x0d,0x00,0x02,0xd2,0xe1,0x01,0x00,0x10,0x0e,0x2c,0x01,0x00,0x40,0xd8,0x1f,0x5f,0xf5,0x6e,0x00,0x00,0x00,0x00,0x00,0x59,0x56,0x47,0x71};
  REQUIRE(decodeSettings(custom3,sizeof(custom3),migrated,&rewrite)&&rewrite);
  REQUIRE(migrated.maxStepRate==3600&&migrated.acceleration==300);
  // Returning to the old speeds deliberately must survive every subsequent boot.
  uint8_t saved[kSettingsBytes];
  migrated.maxStepRate=600;migrated.acceleration=300;
  encodeSettings(migrated,saved);
  REQUIRE(decodeSettings(saved,sizeof(saved),migrated,&rewrite)&&!rewrite);
  REQUIRE(migrated.maxStepRate==600&&migrated.acceleration==300);
  // Compare complete acceleration/cruise/braking moves, not just speed limits.
  for(int32_t distance:{2048,2731}) {
    ++cases;
    const uint32_t previous=measuredMoveTicks(distance,1200,1000);
    const uint32_t twice=measuredMoveTicks(distance,2400,4000);
    const uint32_t fastest=measuredMoveTicks(distance,3600,6000);
    REQUIRE(uint64_t(twice)*100<=uint64_t(previous)*55);
    REQUIRE(fastest<twice);
    std::printf("YAW %ld halfsteps: previous=%luus, 2400/4000=%luus, 3600/6000=%luus (simulation)\n",
                long(distance),static_cast<unsigned long>(previous)*100,
                static_cast<unsigned long>(twice)*100,static_cast<unsigned long>(fastest)*100);
    const uint16_t profiles[][2]={{600,300},{1200,1200},{3600,300},{3600,600},{3600,1200},{3600,6000},{3600,8000},{4800,12000},{7200,24000}};
    constexpr size_t profileCount=sizeof(profiles)/sizeof(profiles[0]);
    uint32_t ticks[profileCount];
    for(size_t i=0;i<profileCount;++i) {
      ticks[i]=measuredMoveTicks(distance,profiles[i][0],profiles[i][1]);
      std::printf("YAW_PROFILE %ld %u %u %luus\n",long(distance),unsigned(profiles[i][0]),
                  unsigned(profiles[i][1]),static_cast<unsigned long>(ticks[i])*100);
    }
    REQUIRE(ticks[1]*100 <= ticks[0]*53);
    REQUIRE(ticks[4]*100 <= ticks[2]*52);
    REQUIRE(ticks[7]*100 <= ticks[5]*72);
    REQUIRE(ticks[8]*100 <= ticks[5]*51);
    for(uint16_t acceleration:{800,1000}) {
      uint32_t oldPeak=0,newPeak=0;
      const uint32_t oldTicks=measuredMoveTicks(distance,3600,acceleration,&oldPeak);
      const uint32_t newTicks=measuredMoveTicks(distance,7200,acceleration,&newPeak);
      REQUIRE(oldTicks==newTicks&&oldPeak==newPeak&&newPeak<3600000);
      std::printf("YAW_LOADED_PROFILE %ld rates=3600,7200 accel=%u time=%luus peak=%lu_milli_halfsteps_per_s\n",
                  long(distance),unsigned(acceleration),static_cast<unsigned long>(newTicks)*100,
                  static_cast<unsigned long>(newPeak));
    }
  }
  ++cases;StepperPlan limits;
  REQUIRE(!limits.start(10,kMaxYawRate+1,1000));
  REQUIRE(!limits.start(10,1200,kMaxYawAcceleration+1));
  Settings s=calibrated();s.maxStepRate=kMaxYawRate;s.acceleration=kMaxYawAcceleration;REQUIRE(validSettings(s));
  s.acceleration=kMaxYawAcceleration+1;REQUIRE(!validSettings(s));s.acceleration=kMaxYawAcceleration;
  for(Profile profile:{Profile::Four13,Profile::Three13}) {
    ++cases;applyProfile(s,profile);Harness h(s,12345);
    REQUIRE(h.c.start(h.ms(),h.us()));h.finish();
    REQUIRE(h.c.stage()==Stage::Complete&&h.c.done()==totalCards(s));
    REQUIRE(h.hw.feedValue==0&&h.hw.ejectValue==0);
    for(uint8_t i=0;i<s.players;++i)REQUIRE(h.c.playerCount(i)==s.cards);
  }
  ++cases;Harness missed(s);
  REQUIRE(missed.c.start(missed.ms(),missed.us()));
  for(unsigned i=0;i<30000 && missed.c.done()<6 && missed.c.stage()!=Stage::Fault;++i)missed.autoStep();
  REQUIRE(missed.c.done()==6);
  missed.homeEnabled=false;missed.finish();
  REQUIRE(missed.c.error()==Error::HomeMissing&&!missed.hw.moving());
  REQUIRE(missed.hw.feedValue==0&&missed.hw.ejectValue==0);
  ++cases;Harness slipped(s);
  slipped.physicalTurnQ16=uint32_t(8252UL*65536);
  REQUIRE(slipped.c.start(slipped.ms(),slipped.us()));slipped.finish();
  REQUIRE(slipped.c.error()==Error::HomeMismatch&&!slipped.hw.moving());
  REQUIRE(slipped.hw.feedValue==0&&slipped.hw.ejectValue==0);
  // Retrieving the same cached PCF byte multiple times is not a new observation.
  ++cases;Harness sample(calibrated());
  const uint32_t us=sample.us(),ms=sample.ms();
  sample.c.tick(ms,us,true,true,false,true);
  sample.c.tick(ms+2,us+2000,true,true,false,false);
  REQUIRE(!sample.c.homeBlocked());
  sample.c.tick(ms+5,us+5000,false,true,false,true);
  REQUIRE(!sample.c.homeBlocked());
  sample.c.tick(ms+10,us+10000,true,true,false,true);
  sample.c.tick(ms+11,us+11000,true,true,false,true);
  REQUIRE(sample.c.homeBlocked());
  REQUIRE(positioningPollMs(3600,5)==1);
}
static void twoStageEjectTests() {
  ++cases;Settings s=calibrated();s.ejectStartPwm=245;s.ejectPwm=155;
  // The first 100 ms straddle millis() rollover.
  Harness h(s,0,(uint64_t(UINT32_MAX)-75)*1000);h.c.start(h.ms(),h.us());h.wait(Stage::SpinUp);
  REQUIRE(h.hw.ejectValue==245&&h.hw.feedValue==0);
  h.edge(true);h.advance(1);h.edge(false);h.advance(4);
  REQUIRE(h.c.stage()==Stage::SpinUp&&h.hw.ejectValue==245&&h.c.done()==0);
  h.advance(94);REQUIRE(h.hw.ejectValue==245&&h.hw.feedValue==0);
  h.advance(1);REQUIRE(h.hw.ejectValue==155&&h.hw.feedValue==0);
  h.advance(79);REQUIRE(h.c.stage()==Stage::SpinUp&&h.hw.feedValue==0);
  h.advance(1);REQUIRE(h.c.stage()==Stage::Feeding&&h.hw.ejectValue==155&&h.hw.feedValue==s.feedPwm);
  h.edge(true);h.advance(3);REQUIRE(h.c.stage()==Stage::Exiting&&h.hw.ejectValue==155);
  REQUIRE(h.hw.feedValue==-175&&h.c.done()==0);
  h.edge(false);h.advance(13);REQUIRE(h.c.stage()==Stage::Tail&&h.hw.ejectValue==155&&h.c.done()==1);
  h.advance(61);REQUIRE(h.c.stage()==Stage::Positioning&&h.hw.ejectValue==0);

  // A late foreground tick changes RF300 first and gives it time to slow down
  // before enabling N20, even if the original 180 ms window has already elapsed.
  ++cases;Harness late(s);late.c.start(late.ms(),late.us());late.wait(Stage::SpinUp);
  late.time+=200000;late.oneMs();REQUIRE(late.hw.ejectValue==155&&late.hw.feedValue==0);
  late.advance(79);REQUIRE(late.c.stage()==Stage::SpinUp&&late.hw.feedValue==0);
  late.advance(1);REQUIRE(late.c.stage()==Stage::Feeding&&late.hw.feedValue==s.feedPwm);

  ++cases;
  const uint8_t old2[]={0x43,0x44,0x52,0x32,0x03,0x0d,0x0d,0x03,0xbe,0xb4,0x01,0x00,0xb0,0x04,0xe8,0x03,0x00,0x40,0xd8,0x1f,0x5f,0x00,0x6e,0x00,0x00,0x00,0x00,0x00,0xb2,0xe8,0x87,0xb5};
  Settings migrated;REQUIRE(decodeSettings(old2,sizeof(old2),migrated));
  REQUIRE(migrated.ejectStartPwm==255&&migrated.ejectPwm==180&&migrated.feedPwm==190);
  REQUIRE(migrated.reversePwm==95&&migrated.reverseMs==110&&migrated.turnQ16==534265856UL);
  REQUIRE(migrated.ejectStartMs==100);
  REQUIRE(migrated.players==3&&migrated.cards==13&&migrated.remainder==13&&migrated.calibrated);
  migrated.ejectStartPwm=39;REQUIRE(!validSettings(migrated));
}
static void ejectDurationSettingsTests() {
  ++cases;
  const uint8_t old4[]={
    0x43,0x44,0x52,0x34,0x04,0x0d,0x00,0x02,0xd2,0xe1,0x01,0x00,0x10,0x0e,0x20,0x03,
    0x00,0x40,0xd8,0x1f,0x5f,0xf5,0x6e,0x00,0x00,0x00,0x00,0x00,0x97,0x8e,0xbe,0xf5
  };
  Settings settings;
  bool needsSave=false;
  REQUIRE(decodeSettings(old4,sizeof(old4),settings,&needsSave)&&needsSave);
  REQUIRE(settings.ejectStartMs==100&&settings.maxStepRate==3600&&settings.acceleration==800);
  REQUIRE(settings.players==4&&settings.cards==13&&settings.remainder==0&&settings.profile==Profile::Four13);
  REQUIRE(settings.calibrated&&settings.turnQ16==534265856UL&&settings.feedPwm==210);
  REQUIRE(settings.ejectStartPwm==245&&settings.ejectPwm==225&&settings.reversePwm==95&&settings.reverseMs==110);
  uint8_t encoded[kSettingsBytes];
  Settings restored;
  for (uint16_t duration:{0,1,37,100,500}) {
    settings.ejectStartMs=duration;
    REQUIRE(validSettings(settings));
    encodeSettings(settings,encoded);
    REQUIRE(decodeSettings(encoded,sizeof(encoded),restored,&needsSave)&&!needsSave);
    REQUIRE(restored.ejectStartMs==duration&&restored.maxStepRate==3600&&restored.acceleration==800);
  }
  settings.ejectStartMs=501;
  REQUIRE(!validSettings(settings));
  encodeSettings(settings,encoded); // A correct checksum cannot make an invalid duration valid.
  REQUIRE(!decodeSettings(encoded,sizeof(encoded),restored,&needsSave));
  REQUIRE(restored.ejectStartMs==500);
}
static void continuousSettingsTests() {
  ++cases;
  const uint8_t old5[]={
    0x43,0x44,0x52,0x35,0x04,0x0d,0x00,0x02,0xaf,0xc8,0x01,0x00,0x10,0x0e,0x20,0x03,
    0x00,0x40,0xd8,0x1f,0xaf,0xfe,0x32,0x00,0x25,0x00,0x00,0x00,0xf5,0x7f,0xad,0xc0
  };
  Settings restored;
  bool rewrite=false;
  REQUIRE(decodeSettings(old5,sizeof(old5),restored,&rewrite)&&rewrite);
  REQUIRE(!restored.continuousYaw && restored.calibrated && restored.turnQ16==534265856UL);
  REQUIRE(restored.releaseTrimMs==0);
  REQUIRE(restored.maxStepRate==3600 && restored.acceleration==800 && restored.ejectStartMs==37);
  REQUIRE(restored.feedPwm==175 && restored.reversePwm==175 && restored.reverseMs==50);
  REQUIRE(restored.ejectPwm==200 && restored.ejectStartPwm==254 && restored.players==4);

  uint8_t bytes[kSettingsBytes];
  restored.continuousYaw=true;
  restored.maxStepRate=1600;
  Settings roundTrip;
  for (int16_t trim:{-150,-10,0,20,150}) {
    restored.releaseTrimMs=trim;
    encodeSettings(restored,bytes);
    REQUIRE(decodeSettings(bytes,sizeof(bytes),roundTrip,&rewrite)&&!rewrite);
    REQUIRE(roundTrip.continuousYaw && roundTrip.maxStepRate==1600 && roundTrip.releaseTrimMs==trim);
    REQUIRE(roundTrip.ejectStartMs==37 && roundTrip.turnQ16==restored.turnQ16);
  }
  for (int16_t invalid:{-151,151,1}) {
    restored.releaseTrimMs=invalid;
    REQUIRE(!validSettings(restored));
    encodeSettings(restored,bytes);
    REQUIRE(!decodeSettings(bytes,sizeof(bytes),roundTrip));
  }
  restored.releaseTrimMs=0;
  for (uint16_t invalid:{99,10001}) {
    restored.maxStepRate=invalid;
    REQUIRE(!validSettings(restored));
  }
}

static Settings continuousSettings(Profile profile=Profile::Four13) {
  Settings settings=calibrated(profile);
  settings.continuousYaw=true;
  settings.maxStepRate=1600;
  settings.acceleration=800;
  return settings;
}

static void continuousRoundTest(Profile profile) {
  ++cases;
  Settings settings=continuousSettings(profile);
  constexpr int32_t origin=12345;
  Harness h(settings,origin);
  REQUIRE(h.c.start(h.ms(),h.us()));
  const uint16_t regular=uint16_t(settings.cards)*settings.players;
  std::vector<int32_t> feedPositions;
  std::vector<uint32_t> releaseTimes;
  std::vector<int32_t> releasePositions;
  for (unsigned ms=0;ms<450000 && h.c.active();++ms) {
    const Stage before=h.c.stage();
    const uint16_t ordinal=h.c.done();
    h.autoStep();
    if (before!=Stage::Feeding && h.c.stage()==Stage::Feeding) {
      feedPositions.push_back(h.hw.position());
      if (ordinal==0 || ordinal>=regular) {
        REQUIRE(!h.hw.moving());
        REQUIRE(h.hw.position()==plannedTarget(settings,origin,ordinal));
      }
      if (ordinal>=2 && ordinal+2<regular) {
        REQUIRE(h.hw.moving());
        REQUIRE(h.hw.position()<plannedTarget(settings,origin,ordinal));
      }
    }
    if (h.c.done()>ordinal) {
      releaseTimes.push_back(h.ms());
      releasePositions.push_back(h.hw.position());
    }
  }
  REQUIRE(h.c.stage()==Stage::Complete && h.c.done()==totalCards(settings));
  REQUIRE(h.c.regularDone()==regular && h.c.remainderDone()==settings.remainder);
  for (uint8_t player=0;player<settings.players;++player) REQUIRE(h.c.playerCount(player)==settings.cards);
  REQUIRE(!h.hw.moving() && h.hw.feedValue==0 && h.hw.ejectValue==0);
  REQUIRE(feedPositions.size()==totalCards(settings) && releasePositions.size()==totalCards(settings));
  for (uint16_t i=2;i+2<regular;++i) {
    const int32_t target=plannedTarget(settings,origin,i);
    // Identical synthetic cards have the same travel time. Check absolute aim on
    // every lap so that wrong player order or a growing phase error cannot pass.
    REQUIRE(releasePositions[i]>target-100 && releasePositions[i]<target+100);
  }
  const uint32_t cruiseInterval=releaseTimes[5]-releaseTimes[4];
  const uint32_t theoreticalMs=8192u*1000/(settings.players*settings.maxStepRate);
  REQUIRE(cruiseInterval+15>=theoreticalMs && cruiseInterval<=theoreticalMs+15);
  std::printf("CONTINUOUS_YAW players=%u rate=%u accel=%u cruise_interval_ms=%lu cards=%u\n",
              unsigned(settings.players),unsigned(settings.maxStepRate),unsigned(settings.acceleration),
              static_cast<unsigned long>(cruiseInterval),unsigned(h.c.done()));
}

static void deliverFirstContinuousCard(Harness& h,unsigned travelMs=60) {
  REQUIRE(h.c.start(h.ms(),h.us()));
  h.wait(Stage::Feeding);
  REQUIRE(!h.hw.moving());
  h.advance(travelMs);
  h.edge(true);h.advance(40);
  REQUIRE(h.c.stage()==Stage::Exiting && h.c.done()==0);
  h.edge(false);h.advance(13);
  REQUIRE(h.c.done()==1 && h.c.stage()==Stage::Tail);
  REQUIRE(h.c.measuredReleaseMs()>=travelMs+40 && h.c.measuredReleaseMs()<=travelMs+55);
}

static void continuousFaultTests() {
  ++cases;
  Harness late(continuousSettings());
  deliverFirstContinuousCard(late);
  late.wait(Stage::Feeding);
  REQUIRE(late.hw.moving());
  // A complete beam pulse counts once on either side of the former ±12° limit.
  late.advance(650);late.card();
  REQUIRE(late.c.error()==Error::None && late.c.done()==2 && late.c.playerCount(1)==1);
  REQUIRE(late.c.phaseErrorSteps()>int32_t(late.c.settings().turnQ16/(30UL*65536)));

  ++cases;
  Harness early(continuousSettings());
  deliverFirstContinuousCard(early,450);
  early.wait(Stage::Feeding);
  REQUIRE(early.hw.moving());
  early.edge(true);early.advance(8);early.edge(false);early.advance(13);
  REQUIRE(early.c.error()==Error::None && early.c.done()==2 && early.c.playerCount(1)==1);
  REQUIRE(early.c.phaseErrorSteps()< -int32_t(early.c.settings().turnQ16/(30UL*65536)));

  ++cases;
  Harness empty(continuousSettings());
  deliverFirstContinuousCard(empty);
  empty.wait(Stage::Feeding);empty.advance(1201);
  REQUIRE(empty.c.error()==Error::NoCard && empty.c.done()==1);
  REQUIRE(!empty.hw.moving() && empty.hw.feedValue==0 && empty.hw.ejectValue==0);

  ++cases;
  Harness jammed(continuousSettings());
  deliverFirstContinuousCard(jammed);
  jammed.wait(Stage::Feeding);jammed.edge(true);jammed.wait(Stage::Exiting);
  jammed.advance(1401);
  REQUIRE(jammed.c.error()==Error::CardStuck && jammed.c.done()==1);
  REQUIRE(!jammed.hw.moving() && jammed.hw.feedValue==0 && jammed.hw.ejectValue==0);

  ++cases;
  Settings slowRoller=continuousSettings();
  slowRoller.cards=2;slowRoller.remainder=2;
  slowRoller.maxStepRate=3000;slowRoller.acceleration=2000;slowRoller.turnQ16=8191UL*65536+32768;
  Harness crossed(slowRoller);
  crossed.physicalTurnQ16=slowRoller.turnQ16;
  deliverFirstContinuousCard(crossed);
  for(uint16_t lap=1;lap<=2;++lap) {
    crossed.wait(Stage::Feeding);crossed.advance(850);
    crossed.edge(true);crossed.wait(Stage::Exiting);crossed.advance(900);
    crossed.edge(false);crossed.wait(Stage::Tail);
    const uint16_t ordinal=2*lap;
    const int32_t seat=plannedTarget(slowRoller,0,ordinal);
    const int32_t oldOffset=int32_t((uint64_t(lap-1)*slowRoller.turnQ16+32768)/65536);
    REQUIRE(crossed.hw.position()>seat+oldOffset && crossed.c.done()==ordinal);
    const size_t commandsBefore=crossed.hw.feedCommands.size();
    crossed.wait(Stage::Feeding);
    // Two extra 8191.5-step laps total exactly 16383 steps.
    const int32_t newOffset=int32_t((uint64_t(lap)*slowRoller.turnQ16+32768)/65536);
    REQUIRE(!crossed.hw.moving() && crossed.hw.position()==seat+newOffset);
    REQUIRE(crossed.c.done()==ordinal);
    for(size_t i=commandsBefore;i+1<crossed.hw.feedCommands.size();++i)REQUIRE(crossed.hw.feedCommands[i]==0);
    crossed.card();
  }
  crossed.finish();
  REQUIRE(crossed.c.stage()==Stage::Complete && crossed.c.done()==10 && crossed.c.remainderDone()==2);
  for(uint8_t i=0;i<4;++i)REQUIRE(crossed.c.playerCount(i)==2);
  std::puts("LANDING_PHASE telemetry_only");

  ++cases;
  Harness missing(continuousSettings());
  missing.homeEnabled=false;
  REQUIRE(missing.c.start(missing.ms(),missing.us()));
  missing.finish();
  REQUIRE(missing.c.error()==Error::HomeMissing && missing.c.homeFault().cause==HomeFault::Missing);
  REQUIRE(!missing.hw.moving() && missing.hw.feedValue==0 && missing.hw.ejectValue==0);

  ++cases;
  Harness aborting(continuousSettings());
  deliverFirstContinuousCard(aborting);
  aborting.wait(Stage::Feeding);
  REQUIRE(aborting.hw.moving());
  aborting.c.abort(aborting.ms());
  REQUIRE(aborting.c.error()==Error::Aborted && aborting.c.done()==1);
  REQUIRE(!aborting.hw.moving() && aborting.hw.feedValue==0 && aborting.hw.ejectValue==0);
}

static void continuousPauseTest() {
  ++cases;
  Settings settings=continuousSettings();
  settings.cards=3;
  Harness paused(settings,12345);
  deliverFirstContinuousCard(paused);
  // Pause while the next card is still in the hopper. The platen may coast
  // past a player's target before it can stop. Resume must keep player order.
  for (int i=0;i<10000 && !paused.hw.moving() && paused.c.active();++i) paused.oneMs();
  REQUIRE(paused.hw.moving() && paused.c.done()==1);
  paused.advance(550);
  REQUIRE(paused.hw.feedValue==0 && paused.hw.moving());
  paused.c.requestPause();
  paused.wait(Stage::Paused);
  REQUIRE(!paused.hw.moving() && paused.hw.feedValue==0 && paused.hw.ejectValue==0);
  const int32_t atRest=paused.hw.position();
  paused.advance(3000);
  REQUIRE(paused.hw.position()==atRest && paused.c.done()==1);
  REQUIRE(paused.c.resume(paused.ms(),paused.us()));
  paused.wait(Stage::Feeding);
  REQUIRE(!paused.hw.moving());
  REQUIRE((paused.hw.position()-plannedTarget(settings,12345,1))%8192==0);
  paused.finish();
  REQUIRE(paused.c.stage()==Stage::Complete && paused.c.done()==12);
  for (uint8_t player=0;player<4;++player) REQUIRE(paused.c.playerCount(player)==3);

  ++cases;
  Harness crossed(settings);
  deliverFirstContinuousCard(crossed);
  crossed.wait(Stage::SpinUp);
  REQUIRE(crossed.hw.moving() && crossed.hw.feedValue==0);
  crossed.c.requestPause();
  crossed.wait(Stage::Paused);
  const int32_t nextPlayer=plannedTarget(settings,0,1);
  REQUIRE(crossed.hw.position()>nextPlayer && crossed.c.done()==1);
  REQUIRE(crossed.c.resume(crossed.ms(),crossed.us()));
  crossed.wait(Stage::Feeding);
  REQUIRE(!crossed.hw.moving() && crossed.hw.position()==nextPlayer+8192);
  crossed.finish();
  REQUIRE(crossed.c.stage()==Stage::Complete && crossed.c.done()==12);
  for (uint8_t player=0;player<4;++player) REQUIRE(crossed.c.playerCount(player)==3);

  ++cases;
  Harness inFlight(settings);
  deliverFirstContinuousCard(inFlight);
  inFlight.wait(Stage::Feeding);
  inFlight.c.requestPause();
  inFlight.advance(60);
  inFlight.edge(true);inFlight.advance(40);
  REQUIRE(inFlight.c.stage()==Stage::Exiting && inFlight.hw.moving());
  inFlight.edge(false);
  inFlight.wait(Stage::Paused);
  REQUIRE(inFlight.c.done()==2 && !inFlight.hw.moving());
  REQUIRE(inFlight.hw.feedValue==0 && inFlight.hw.ejectValue==0);
  REQUIRE(inFlight.c.resume(inFlight.ms(),inFlight.us()));
  inFlight.finish();
  REQUIRE(inFlight.c.stage()==Stage::Complete && inFlight.c.done()==12);
}

static int32_t feedPositionWithTrim(int16_t trim) {
  Settings s=continuousSettings();
  s.releaseTrimMs=trim;
  Harness h(s);
  REQUIRE(h.c.start(h.ms(),h.us()));
  for (unsigned i=0;i<20000 && h.c.active();++i) {
    h.autoStep();
    if (h.c.done()==4 && h.c.stage()==Stage::Feeding) return h.hw.position();
  }
  REQUIRE(false); // The fifth card should have reached the constant-speed portion.
  return 0;
}

static void continuousTrimTest() {
  ++cases;
  const int32_t untrimmed=feedPositionWithTrim(0);
  const int32_t earlier=feedPositionWithTrim(60);
  const int32_t later=feedPositionWithTrim(-60);
  // At 1600 half-steps/s, 60 ms advances/retards the feed by 96 steps.
  REQUIRE(earlier>=untrimmed-102 && earlier<=untrimmed-90);
  REQUIRE(later>=untrimmed+90 && later<=untrimmed+102);
  // Both ends of the trim setting shift the intended outlet heading.
  for (int16_t trim:{-150,150}) {
    ++cases;
    Settings s=continuousSettings();
    s.releaseTrimMs=trim;s.maxStepRate=2000;s.turnQ16=6000UL*65536;
    Harness h(s,500,(uint64_t(UINT32_MAX)-2500)*1000);
    h.physicalTurnQ16=s.turnQ16;
    REQUIRE(h.c.start(h.ms(),h.us()));
    for (unsigned i=0;i<180000 && h.c.active();++i) {
      const uint16_t before=h.c.done();
      h.autoStep();
      if(before==6 && h.c.done()==7) {
        const int32_t expected=-int32_t(s.maxStepRate)*trim/1000;
        REQUIRE(std::abs(h.c.phaseErrorSteps()-expected)<=15);
      }
    }
    REQUIRE(h.c.stage()==Stage::Complete && h.c.done()==52);
  }
}

struct SampledOutletEdge {
  uint32_t ms,us;
  int32_t position;
};

// The motion ISR continues to advance while a busy foreground cannot drain
// the queue. The outlet qualifier has already validated these transitions.
static SampledOutletEdge advanceWhileForegroundBusy(Harness& h,unsigned ms) {
  for (unsigned i=0;i<ms*10;++i) {h.hw.plan.tick();h.time+=100;}
  return {h.ms(),h.us(),h.hw.position()};
}

static void delayedQualifiedOutletTests() {
  ++cases;
  Harness h(continuousSettings(),0,(uint64_t(UINT32_MAX)-400)*1000);
  REQUIRE(h.c.start(h.ms(),h.us()));
  for (unsigned ordinal=0;ordinal<2;++ordinal) {
    h.wait(Stage::Feeding);
    REQUIRE(h.hw.moving()==(ordinal==1));
    const SampledOutletEdge leading=advanceWhileForegroundBusy(h,60);
    const SampledOutletEdge trailing=advanceWhileForegroundBusy(h,40);
    const auto processing=advanceWhileForegroundBusy(h,220);
    const int32_t expected=trailing.position-h.c.target();
    if (ordinal==1) {
      REQUIRE(std::abs(expected)<25);
      REQUIRE(processing.position-h.c.target()>int32_t(kNominalTurnQ16/(30UL*65536)));
    }
    h.c.qualifiedExitEdge(true,leading.us,leading.ms,leading.position,processing.ms);
    REQUIRE(h.c.stage()==Stage::Exiting && h.c.done()==ordinal);
    h.c.qualifiedExitEdge(false,trailing.us,trailing.ms,trailing.position,processing.ms);
    REQUIRE(h.c.stage()==Stage::Tail && h.c.done()==ordinal+1 && !h.c.exitBlocked());
    REQUIRE(h.c.measuredReleaseMs()==100 && h.c.phaseErrorSteps()==expected);
    h.oneMs();
    REQUIRE(h.c.error()==Error::None && h.c.done()==ordinal+1);
  }

  ++cases;
  Harness stale(continuousSettings());
  REQUIRE(stale.c.start(stale.ms(),stale.us()));
  stale.wait(Stage::Feeding);
  const uint32_t startMs=stale.ms(),startUs=stale.us();
  stale.advance(4);
  // A qualified leading edge from before feed, even in the same millisecond,
  // must not arm the following clear edge to count a card.
  stale.c.qualifiedExitEdge(true,startUs-1,startMs,stale.hw.position(),stale.ms());
  REQUIRE(stale.c.error()==Error::None && stale.c.stage()==Stage::Feeding && stale.c.done()==0);
  REQUIRE(stale.c.unexpectedExit().count==1 && stale.c.unexpectedExit().lastStage==Stage::Feeding);
  REQUIRE(stale.hw.feedValue==stale.c.settings().feedPwm);
  stale.c.qualifiedExitEdge(false,startUs+2000,startMs+2,stale.hw.position(),stale.ms());
  REQUIRE(stale.c.done()==0 && stale.c.stage()==Stage::Feeding);
  stale.card();REQUIRE(stale.c.done()==1 && stale.c.unexpectedExit().count==1);
  stale.c.abort(stale.ms());stale.c.clearFault(stale.ms());stale.advance(25);
  REQUIRE(stale.c.start(stale.ms(),stale.us()) && stale.c.unexpectedExit().count==0);
  std::printf("E06 telemetry_only\n");
}

static void yawPercentTests() {
  ++cases;
  Settings s=calibrated();
  uint8_t record[kSettingsBytes];
  Settings decoded;
  bool rewrite=false;
  uint16_t rate=kMinYawRate;
  for(unsigned pct=1;pct<=100;++pct) {
    REQUIRE(rate==pct*kYawRatePerPercent);
    s.maxStepRate=rate;
    REQUIRE(validSettings(s));
    encodeSettings(s,record);
    REQUIRE(decodeSettings(record,sizeof(record),decoded,&rewrite) && !rewrite && decoded.maxStepRate==rate);
    rate=nextYawRate(rate,+1);
  }
  REQUIRE(rate==10000 && nextYawRate(rate,+1)==rate);
  for(int pct=100;pct>=1;--pct) {REQUIRE(rate==pct*kYawRatePerPercent);rate=nextYawRate(rate,-1);}
  REQUIRE(rate==100 && nextYawRate(rate,-1)==rate);
  REQUIRE(nextYawRate(650,+1)==700 && nextYawRate(650,-1)==600);

  ++cases;
  const uint8_t stopped[]={0x43,0x44,0x52,0x36,0x04,0x0d,0x00,0x02,0xaf,0xc8,0x01,0x0f,0x8a,0x02,0x20,0x03,
                           0x00,0x40,0xd8,0x1f,0xaf,0xfe,0x32,0x00,0x25,0x00,0x14,0x05,0x0b,0x19,0x9a,0x66};
  const uint8_t moving[]={0x43,0x44,0x52,0x36,0x04,0x0d,0x00,0x02,0xaf,0xc8,0x01,0x8f,0x8a,0x02,0x20,0x03,
                          0x00,0x40,0xd8,0x1f,0xaf,0xfe,0x32,0x00,0x25,0x00,0x14,0x05,0xe3,0xd2,0x16,0xdc};
  for(const auto* old:{stopped,moving}) {
    const uint16_t expected=old==moving?1300:650;
    REQUIRE(decodeSettings(old,sizeof(stopped),s,&rewrite) && rewrite);
    REQUIRE(s.calibrated && s.ejectStartMs==37 && s.continuousYaw==(old==moving) && s.maxStepRate==expected);
    encodeSettings(s,record);
    REQUIRE(decodeSettings(record,sizeof(record),decoded,&rewrite) && !rewrite && decoded.maxStepRate==expected);
  }

  ++cases;
  StepperPlan plan;
  REQUIRE(plan.start(18000,10000,24000));
  unsigned consecutive=0,longest=0,total=0;
  for(unsigned tick=0;plan.busy() && tick<100000;++tick) {
    if(plan.tick()) {++total;++consecutive;if(consecutive>longest)longest=consecutive;}
    else consecutive=0;
  }
  REQUIRE(total==18000 && plan.position()==18000 && !plan.busy());
  REQUIRE(longest>10000); // One half-step every single 100 us tick at 100%.
  std::printf("YAW_PERCENT max=100 peak_halfsteps_per_s=10000 consecutive_cruise_ticks=%u\n",longest);

  for(bool sweep:{false,true})for(uint16_t limit:{100,10000}) {
    ++cases;
    Settings config=continuousSettings();
    config.cards=2;config.continuousYaw=sweep;config.maxStepRate=limit;
    config.acceleration=24000;config.ejectStartMs=0;
    Harness h(config,0,(uint64_t(UINT32_MAX)-150)*1000);
    REQUIRE(h.c.start(h.ms(),h.us()));
    h.wait(Stage::Feeding);
    h.edge(true);h.advance(5);h.edge(false);h.advance(13);
    REQUIRE(h.c.done()==1);
    h.wait(Stage::Positioning);
    REQUIRE(h.hw.moving() && h.hw.commandedRate==limit && h.hw.commandedAccel==24000);
    REQUIRE(h.c.sweeping()==sweep);
    h.c.abort(h.ms());
    REQUIRE(!h.hw.moving() && h.c.error()==Error::Aborted);
  }
}

static void yawDirectionTests() {
  ++cases;
  static_assert(kSettingsBytes==32,"The settings blob in NVS and stored flight reports must keep its length");
  const uint8_t cdr7[]={0x43,0x44,0x52,0x37,0x03,0x11,0x03,0x00,0xe6,0xd2,0x01,0x8f,0xe8,0x03,0x64,0x00,
                         0x00,0x80,0xff,0x1f,0xc8,0xff,0x50,0x00,0x18,0x01,0x00,0x00,0xe5,0xe6,0x72,0xbd};
  Settings s;
  bool rewrite=false;
  REQUIRE(!s.counterclockwise && decodeSettings(cdr7,sizeof(cdr7),s,&rewrite) && rewrite);
  REQUIRE(!s.counterclockwise && s.maxStepRate==1000 && s.acceleration==100 && s.continuousYaw);
  REQUIRE(s.turnQ16==kDeviceTurnQ16 && s.ejectPwm==210 && s.ejectStartMs==280);
  uint8_t bytes[kSettingsBytes];
  for(bool ccw:{false,true}) {
    s.counterclockwise=ccw;
    applyProfile(s,Profile::Guandan);
    REQUIRE(s.counterclockwise==ccw);
    encodeSettings(s,bytes);
    REQUIRE(memcmp(bytes,"CDR8",4)==0 && bytes[26]==unsigned(ccw) && bytes[27]==0);
    Settings decoded;
    REQUIRE(decodeSettings(bytes,sizeof(bytes),decoded,&rewrite) && !rewrite && decoded.counterclockwise==ccw);
  }
  // Independent CRC-valid CDR8 fixtures with an illegal flag or reserved byte.
  std::memcpy(bytes,cdr7,sizeof(bytes));
  bytes[3]='8';
  for(const auto& tail:{std::vector<uint8_t>{2,0,0x78,0xeb,0x1f,0x6d},
                        std::vector<uint8_t>{0,1,0x6c,0xb9,0x2e,0x28}}) {
    std::memcpy(bytes+26,tail.data(),tail.size());
    REQUIRE(!decodeSettings(bytes,sizeof(bytes),s));
  }

  ++cases;
  Harness h(calibrated());
  REQUIRE(h.hw.moveTo(3,500,500));
  h.advance(100);
  REQUIRE(!h.hw.moving() && h.hw.position()==3 && h.hw.plan.phase()==3);
  h.hw.hold(true);
  Settings reverse=h.c.settings();reverse.counterclockwise=true;
  REQUIRE(h.c.configure(reverse));
  REQUIRE(h.hw.holding && h.hw.position()==3 && h.hw.plan.phase()==3);
  REQUIRE(h.hw.moveTo(5,500,500));
  REQUIRE(!h.c.configure(calibrated()));
  h.advance(100);
  REQUIRE(!h.hw.moving() && h.hw.position()==5 && h.hw.plan.phase()==1 && h.shaftTravel==1);

  for(bool ccw:{false,true})for(bool continuous:{false,true})for(uint8_t players:{3,4}) {
    ++cases;
    Settings game=calibrated();game.players=players;game.cards=2;game.remainder=2;
    game.counterclockwise=ccw;game.continuousYaw=continuous;
    Harness run(game,0,0,false,kDeviceTurnQ16);
    Settings opposite=game;opposite.counterclockwise=!ccw;
    REQUIRE(run.c.start(run.ms(),run.us()) && !run.c.configure(opposite));
    const int sign=ccw?-1:1;
    for(unsigned tick=0;run.c.active() && tick<120000;++tick) {
      const uint16_t previous=run.c.done();
      run.autoStep();
      if(run.c.done()!=previous) {
        const int32_t expected=plannedTarget(run.c.settings(),0,previous);
        REQUIRE(run.shaftTravel==sign*run.hw.position());
        REQUIRE(std::abs(run.shaftTravel-sign*expected)<=100);
      }
    }
    REQUIRE(run.c.stage()==Stage::Complete && run.c.done()==totalCards(game));
    REQUIRE(run.c.remainderDone()==2 && run.c.homeFault().cause==HomeFault::None);
    const int32_t midpoint=plannedTarget(run.c.settings(),0,game.cards*players);
    REQUIRE(run.shaftTravel==sign*midpoint);
    for(uint8_t seat=0;seat<players;++seat)REQUIRE(run.c.playerCount(seat)==2);
  }
  ++cases;
  Harness ccwCal(reverse,0,0,false,kDeviceTurnQ16);
  REQUIRE(ccwCal.c.calibrate(ccwCal.ms(),ccwCal.us()));
  ccwCal.wait(Stage::Idle,120000);
  REQUIRE(ccwCal.c.calibrationTurns()==4 && ccwCal.shaftTravel<0);
  REQUIRE(ccwCal.c.settings().turnQ16==kDeviceTurnQ16);
  std::printf("YAW_DIRECTION cw_ccw_settings_and_phase=pass players=3,4 modes=stop,sweep remainder=midpoint\n");
}

int main() {
  settingsTests();exactAngleTests();roundTest(Profile::Landlord);roundTest(Profile::Guandan);roundTest(Profile::Four13);roundTest(Profile::Three13);
  pauseAbortTests();pauseBeforeFeedTest();jamTests();sensorTests();communicationTests();referenceTests();calibrationTests();wrapTests();buttonTests();stepperTests();
  reverseTests();migrationAndSpeedTests();
  fasterYawTests();
  twoStageEjectTests();ejectDurationSettingsTests();continuousSettingsTests();
  calibrationTraceTests();
  static_assert(kDeviceTurnQ16==536838144UL,"Device reported 8191.5000 half-steps per turn");
  fixedTurnTests(kDeviceTurnQ16);
  yawPercentTests();
  yawDirectionTests();
  for (Profile profile:{Profile::Landlord,Profile::Guandan,Profile::Four13,Profile::Three13}) continuousRoundTest(profile);
  continuousFaultTests();continuousPauseTest();continuousTrimTest();delayedQualifiedOutletTests();
  std::printf("PASS %u scenarios, %u assertions; actual DealerCore.cpp and StepperPlan.h executed\n",cases,checks);return 0;
}
