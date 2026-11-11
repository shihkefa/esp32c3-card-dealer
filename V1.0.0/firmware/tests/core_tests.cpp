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
  StepperPlan plan;int32_t offset=0;int16_t feedValue=0;uint8_t ejectValue=0;bool holding=false;
  std::vector<int32_t> targets;
  bool moveTo(int32_t target,uint16_t s,uint16_t a) override {targets.push_back(target);return plan.start(target-offset,s,a);}
  int32_t position() const override{return offset+plan.position();}
  bool moving() const override{return plan.busy();}
  void stopMotion() override{plan.stop();}
  void hold(bool b) override{holding=b;}
  void feed(int16_t v) override{feedValue=v;}
  void eject(uint8_t v) override{ejectValue=v;}
};
struct Harness {
  FakeHardware hw;Controller c;uint64_t time=0;uint32_t physicalTurnQ16=kNominalTurnQ16;
  bool homeEnabled=true,homeStuck=false,homeSample=false;
  uint32_t homePollAt=0;bool rawExit=false;bool cardScheduled=false,cardBlocked=false;
  uint64_t cardStart=0;
  explicit Harness(Settings s=Settings{},int32_t offset=0,uint64_t initial=0,bool blocked=false):c(hw),time(initial),rawExit(blocked) {
    hw.offset=offset;c.begin(s,blocked,false,ms(),us());advance(30);
  }
  uint32_t ms() const{return uint32_t(time/1000);}
  uint32_t us() const{return uint32_t(time);}
  void edge(bool v,uint32_t stamp=0) {rawExit=v;c.rawExitEdge(v,stamp?stamp:us(),ms());}
  void oneMs(bool io=true,bool overflow=false) {
    for(int i=0;i<10;++i){hw.plan.tick();time+=100;}
    if(uint32_t(ms()-homePollAt)>=5) {
      homePollAt=ms();
      const int64_t p=(int64_t(hw.position()-100)*65536)%physicalTurnQ16;
      const int64_t phase=p<0?p+physicalTurnQ16:p;
      homeSample=homeStuck||(homeEnabled&&phase<50*65536);
    }
    c.tick(ms(),us(),homeSample,io,overflow);
  }
  void advance(unsigned n,bool io=true){for(unsigned i=0;i<n;++i)oneMs(io);}
  void wait(Stage s,unsigned maxMs=20000) {
    for(unsigned i=0;i<maxMs&&c.stage()!=s&&c.stage()!=Stage::Fault;++i)oneMs();
    REQUIRE(c.stage()==s);
  }
  void card() {
    wait(Stage::Feeding);edge(true);advance(3);REQUIRE(c.stage()==Stage::Exiting);REQUIRE(hw.feedValue==0);
    advance(30);edge(false);advance(4);REQUIRE(c.stage()==Stage::Tail);
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
  h.c.rawExitEdge(true,at+2000,h.ms());h.c.rawExitEdge(false,at+10000,h.ms());h.oneMs();
  REQUIRE(h.c.done()==1&&h.c.stage()==Stage::Tail);
  h.edge(true);h.advance(3);REQUIRE(h.c.error()==Error::UnexpectedCard&&h.c.done()==1);
  Harness y(calibrated());y.c.start(y.ms(),y.us());y.card();y.advance(65);REQUIRE(y.c.stage()==Stage::Positioning);
  y.edge(true);y.advance(3);REQUIRE(y.c.error()==Error::UnexpectedCard&&!y.hw.moving());
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
  Harness stuck(calibrated());stuck.homeStuck=true;stuck.advance(10);stuck.c.start(stuck.ms(),stuck.us());stuck.finish();
  REQUIRE(stuck.c.error()==Error::HomeMissing);
  Harness wrong(calibrated());wrong.physicalTurnQ16=8500UL*65536;wrong.c.start(wrong.ms(),wrong.us());wrong.finish();
  REQUIRE(wrong.c.error()==Error::HomeMismatch);
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
int main() {
  settingsTests();exactAngleTests();roundTest(Profile::Landlord);roundTest(Profile::Guandan);roundTest(Profile::Four13);roundTest(Profile::Three13);
  pauseAbortTests();pauseBeforeFeedTest();jamTests();sensorTests();communicationTests();referenceTests();calibrationTests();wrapTests();buttonTests();stepperTests();
  std::printf("PASS %u scenarios, %u assertions; actual DealerCore.cpp and StepperPlan.h executed\n",cases,checks);return 0;
}
