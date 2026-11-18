#include "FlightLog.h"
#include <SPIFFS.h>
#include <esp_rom_crc.h>
#include <cstdio>
#include <cstdlib>
#include <limits>
using namespace flight;
using namespace dealer;

static unsigned cases=0,checks=0;
#define CHECK(test) do{++checks;if(!(test)){std::fprintf(stderr,"FAIL %s:%d %s\n",__FILE__,__LINE__,#test);std::exit(1);}}while(false)

struct InstantMotion: Hardware {
  int32_t pos=0; bool blocked=false;
  bool moveTo(int32_t p,uint16_t,uint16_t) override {pos=p;return true;}
  int32_t position() const override {return pos;}
  bool moving() const override {return false;}
  void setCounterclockwise(bool) override {}
  bool outletRawBlocked() const override {return blocked;}
  void stopMotion() override {} void hold(bool) override {}
  void feed(int16_t) override {} void eject(uint8_t) override {}
};

struct Deal {
  InstantMotion hw;
  Controller controller{hw};
  Recorder recorder;
  Counters counters{54,36,2};
  uint32_t now=UINT32_MAX-50,started=0;
  void begin(bool calibrated=true) {
    Settings s; s.calibrated=calibrated;s.cards=1;s.remainder=1;
    controller.begin(s,false,false,now,now*1000);
    advance(21);
    recorder.begin(Kind::Deal,s,now,hw.position(),counters);started=now;
    CHECK(controller.start(now,now*1000)==calibrated);
    recorder.stage(controller,now);
  }
  void advance(unsigned duration) {
    while(duration--) {
      ++now;controller.tick(now,now*1000,false,true);recorder.stage(controller,now);
    }
  }
  void wait(Stage stage) {
    unsigned n=0;
    while(controller.stage()!=stage && n++<2000) advance(1);
    CHECK(controller.stage()==stage);
  }
  void edge(bool blocked) {
    ++counters.raw;++counters.qualified;
    hw.blocked=blocked;
    recorder.edge(controller,blocked,now*1000,now,hw.position());
    controller.qualifiedExitEdge(blocked,now*1000,now,hw.position(),now);
    recorder.stage(controller,now);
  }
  void finish(Result result) {
    recorder.finish(controller,result,now,hw.position(),counters);
    CHECK(!recorder.recording);
  }
};

static void recordCards() {
  ++cases;
  Deal d;d.begin();
  for(unsigned i=0;i<4;++i) {
    d.wait(Stage::Feeding);
    const auto feedMs=d.now-d.started;
    d.advance(40);d.edge(true);d.advance(50);d.edge(false);d.wait(Stage::Tail);
    const auto& r=d.recorder.report.rows[i];
    CHECK(r.spinMs>=0 && r.feedMs>r.spinMs && uint32_t(r.feedMs)==feedMs);
    CHECK(r.blockedMs==r.feedMs+40 && r.clearMs==r.feedMs+90 && r.countMs>=r.clearMs);
    CHECK(r.qualifiedEdges==2 && r.releaseMs==r.countMs-r.feedMs);
    CHECK(r.target==plannedTarget(d.controller.settings(),0,i));
    CHECK(r.target==r.blockedPosition && r.target==r.clearPosition && r.phaseError==0);
    CHECK(r.player==(i==3?0:i+1));
  }
  d.wait(Stage::Complete);d.finish(Result::Complete);
  const Header& h=d.recorder.report.header;
  CHECK(h.rowCount==4 && h.regularDone==3 && h.extraDone==1);
  CHECK(h.elapsedMs==d.now-d.started && h.startMs==d.started && h.finalTarget==d.hw.pos);
  CHECK(h.rawEdges==8 && h.qualifiedEdges==8 && h.overflows==0);
  Settings restored;CHECK(decodeSettings(h.settings,kSettingsBytes,restored)&&restored.calibrated);
}

static void recordPartial() {
  ++cases;
  Deal d;d.begin();d.wait(Stage::Feeding);d.edge(true);d.advance(5);
  d.controller.abort(d.now);d.finish(Result::Aborted);
  const Header& h=d.recorder.report.header;const Card& r=d.recorder.report.rows[0];
  CHECK(h.result==Result::Aborted && h.error==Error::Aborted && h.faultStage==Stage::Exiting);
  CHECK(h.rowCount==1 && h.regularDone==0 && h.exitBlocked && h.qualifiedEdges==1);
  CHECK(r.feedMs>=0 && r.blockedMs>=0 && r.clearMs==-1 && r.countMs==-1);
  ++cases;
  Deal rejected;rejected.begin(false);rejected.finish(Result::Rejected);
  CHECK(rejected.recorder.report.header.error==Error::NeedCalibration);
  CHECK(rejected.recorder.report.header.rowCount==0);
  ++cases;
  d.recorder.begin(Kind::IdleFault,d.controller.settings(),d.now,d.hw.pos,d.counters);
  d.recorder.edge(d.controller,true,d.now*1000,d.now,d.hw.pos);
  d.finish(Result::Fault);
  CHECK(d.recorder.report.header.kind==Kind::IdleFault && d.recorder.report.header.rowCount==0);
  ++cases;
  d.recorder.begin(Kind::Calibration,d.controller.settings(),d.now,d.hw.pos,d.counters);
  d.finish(Result::Aborted);CHECK(d.recorder.report.header.kind==Kind::Calibration);
  CHECK(d.recorder.report.header.calibratedTurnQ16==d.controller.settings().turnQ16);
}

static Report makeReport(unsigned marker,unsigned rows=108) {
  Report r{};
  Settings s;s.calibrated=true;s.continuousYaw=true;s.releaseTrimMs=-40;
  encodeSettings(s,r.header.settings);
  r.header.startMs=marker;r.header.rowCount=uint16_t(rows);
  for(unsigned i=0;i<rows;++i) {
    auto& row=r.rows[i];row.feedMs=i*175;row.clearMs=row.feedMs+95;
    row.player=i%4+1;row.target=marker+2048*i;row.qualifiedEdges=2;
  }
  return r;
}
static void recordUnexpectedExit() {
  ++cases;
  Deal d;d.begin();d.wait(Stage::SpinUp);
  d.edge(true);d.advance(10);d.edge(false);
  d.wait(Stage::Feeding);d.advance(30);
  const int32_t leading=int32_t(d.now-d.started);
  d.edge(true);d.advance(30);d.edge(false);d.wait(Stage::Tail);
  d.edge(true);d.advance(5);d.edge(false);
  d.controller.abort(d.now);d.finish(Result::Aborted);
  const auto& h=d.recorder.report.header;
  CHECK(h.unexpectedCount==2 && h.unexpectedLastStage==Stage::Tail);
  CHECK(h.qualifiedEdges==6 && h.regularDone==1 && h.rowCount==1);
  const auto& card=d.recorder.report.rows[0];
  CHECK(card.qualifiedEdges==2 && card.blockedMs==leading && card.clearMs==leading+30);
}
static void freshStorage() {
  testfs::files.clear();testfs::formatted=false;testfs::mountFailure=false;testfs::denyWrite=false;
  testfs::partition.assign(4096,0xff);testfs::formats=0;
  testfs::writeBudget=std::numeric_limits<size_t>::max();
  CHECK(mount());CHECK(testfs::formats==1 && !stored());
}
static void checkRanks(unsigned newest,unsigned count) {
  CHECK(stored()==count);
  Report out{};CHECK(!load(0,out) && !load(count+1,out));
  for(unsigned rank=1;rank<=count;++rank) {
    CHECK(load(rank,out)); const unsigned id=newest-rank+1;
    CHECK(out.header.sequence==id && out.header.startMs==100+id);
    CHECK(out.header.rowCount==108);
    for(unsigned i=0;i<108;++i) {
      const auto& row=out.rows[i];
      CHECK(row.player==i%4+1 && row.target==int32_t(100+id+i*2048));
      CHECK(row.feedMs==int32_t(i*175) && row.clearMs==row.feedMs+95 && row.qualifiedEdges==2);
    }
  }
}
static void convertTestSlotToLegacy(const char* path) {
  auto& bytes=testfs::files.at(path);
  const uint32_t legacyMagic=0x31474C44;
  constexpr size_t oldHeaderSize=104;
  bytes.erase(bytes.begin()+oldHeaderSize,bytes.begin()+sizeof(Header));
  std::memcpy(bytes.data(),&legacyMagic,sizeof(legacyMagic));
  const size_t body=bytes.size()-sizeof(uint32_t);
  const uint32_t crc=esp_rom_crc32_le(0,bytes.data(),body);
  std::memcpy(bytes.data()+body,&crc,sizeof(crc));
}
static void legacyArchive() {
  ++cases;freshStorage();
  auto game=makeReport(55,2);game.header.error=Error::UnexpectedCard;game.header.result=Result::Fault;
  game.header.faultStage=Stage::Tail;CHECK(save(game));
  CalibrationReport cal{};cal.header.kind=Kind::Calibration;cal.count=1;cal.samples[0]={56,200};
  CHECK(saveCalibration(cal));
  convertTestSlotToLegacy("/dealer-flight-0");convertTestSlotToLegacy("/dealer-cal-0");
  auto newer=makeReport(56,2);newer.header.unexpectedCount=3;newer.header.unexpectedLastStage=Stage::Feeding;
  CHECK(save(newer));CHECK(mount());
  Report restored{};CHECK(load(1,restored));
  CHECK(restored.header.magic==Header{}.magic && restored.header.unexpectedCount==3 &&
        restored.header.unexpectedLastStage==Stage::Feeding);
  CHECK(load(2,restored));CHECK(restored.header.magic==kLegacyLogMagic && restored.header.unexpectedCount==0);
  CHECK(restored.header.error==Error::UnexpectedCard && restored.header.rowCount==2 && restored.rows[1].feedMs==175);
  CalibrationReport oldCal{};CHECK(loadCalibrationForExport(1,nullptr,oldCal));
  CHECK(oldCal.header.magic==kLegacyLogMagic && oldCal.count==1 && oldCal.samples[0].position==56);
  testfs::files.at("/dealer-flight-0").back()^=1;
  CHECK(mount() && stored()==1 && calibrationsStored()==1);
}
static testfs::Bytes& bytesFor(unsigned id) {
  for(auto& file:testfs::files) {
    Header header;
    if(file.second.size()<sizeof(header))continue;
    std::memcpy(&header,file.second.data(),sizeof(header));
    if(header.sequence==id)return file.second;
  }
  std::abort();
}
static void ringAndPowerLoss() {
  ++cases;freshStorage();
  for(unsigned id=1;id<=7;++id) {
    auto r=makeReport(100+id);CHECK(save(r));CHECK(r.header.sequence==id);
    checkRanks(id,std::min(id,4U));
  }
  CHECK(mount() && testfs::formats==1);checkRanks(7,4);
  const auto expected=sizeof(Header)+108*sizeof(Card)+sizeof(uint32_t);
  for(size_t limit:{size_t(0),size_t(11),expected/2,expected-1}) {
    ++cases;
    testfs::writeBudget=limit;
    Report next=makeReport(108);CHECK(!save(next));
    CHECK(std::string(storageState())=="write-failed-RAM-only");
    checkRanks(7,4);
    CHECK(mount());checkRanks(7,4);
  }
  testfs::writeBudget=std::numeric_limits<size_t>::max();
  auto r=makeReport(108);CHECK(save(r));CHECK(mount());checkRanks(8,4);
  ++cases;
  bytesFor(8)[sizeof(Header)+sizeof(Card)*3+1]^=0x04;
  Report out{};CHECK(!load(1,out));CHECK(mount());checkRanks(7,4);
  ++cases;
  bytesFor(7).pop_back();CHECK(mount());checkRanks(6,3);
  ++cases;
  auto& bytes=bytesFor(6);
  Header invalid;std::memcpy(&invalid,bytes.data(),sizeof(invalid));invalid.kind=Kind(250);
  std::memcpy(bytes.data(),&invalid,sizeof(invalid));
  uint32_t newCrc=esp_rom_crc32_le(0,bytes.data(),bytes.size()-sizeof(uint32_t));
  std::memcpy(bytes.data()+bytes.size()-sizeof(uint32_t),&newCrc,sizeof(newCrc));
  CHECK(mount());checkRanks(5,2);
}
static void ramFallback() {
  ++cases;freshStorage();
  for(unsigned id=1;id<=4;++id){auto r=makeReport(100+id);CHECK(save(r));}
  testfs::denyWrite=true;
  auto ram=makeReport(999);CHECK(!save(ram));
  Report out{};
  CHECK(loadForExport(1,&ram,out) && out.header.startMs==999);
  for(unsigned rank=2;rank<=4;++rank)
    CHECK(loadForExport(rank,&ram,out) && out.header.sequence==6-rank);
  CHECK(!loadForExport(0,&ram,out) && !loadForExport(5,&ram,out));
  CHECK(loadForExport(1,nullptr,out) && out.header.sequence==4);
  CHECK(loadForExport(2,nullptr,out) && out.header.sequence==3);
  CHECK(mount());checkRanks(4,4);
  ++cases;
  // Nonblank partition with an unreadable filesystem must never be formatted.
  testfs::formatted=false;
  CHECK(!mount() && testfs::formats==1);
  CHECK(std::string(storageState())=="unavailable-RAM-only");
  CHECK(!save(ram) && !load(1,out));
  CHECK(loadForExport(1,&ram,out) && out.header.startMs==999);
  CHECK(!loadForExport(2,&ram,out));
}
struct CalibrationMotion:InstantMotion {
  bool running=false;
  bool moveTo(int32_t,uint16_t,uint16_t) override {running=true;return true;}
  void stopMotion() override {running=false;}
  bool moving() const override {return running;}
};
static CalibrationReport recordCalibration(const std::vector<int32_t>& positions,Result result,uint32_t fixedTurn=0) {
  CalibrationMotion hw;Controller c(hw,fixedTurn);Recorder recorder;Settings settings;
  uint32_t ms=UINT32_MAX-90;c.begin(settings,false,false,ms,ms*1000);
  ms+=30;c.tick(ms,ms*1000,false,true);const uint32_t start=ms;
  recorder.begin(Kind::Calibration,c.settings(),start,0,{0,0,0});
  CHECK(c.calibrate(ms,ms*1000));
  auto tick=[&](bool blocked){c.tick(ms,ms*1000,blocked,true);recorder.stage(c,ms);};
  for(auto pos:positions){
    hw.pos=pos;ms+=38;tick(true);++ms;tick(true);++ms;tick(false);
    ++ms;tick(false);
  }
  if(result==Result::Aborted)c.abort(ms);
  recorder.finish(c,result,ms,hw.pos,{0,0,0});
  auto& r=recorder.calibration;
  CHECK(r.header.kind==Kind::Calibration && r.header.result==result && r.count==positions.size());
  for(unsigned i=0;i<r.count;++i)
    CHECK(r.samples[i].position==positions[i] && r.samples[i].elapsedMs==38+i*41);
  return r;
}
static void calibrationArchive() {
  ++cases;freshStorage();
  auto good=recordCalibration({500,8652,16805,24957,33109},Result::Complete);
  CHECK(good.header.error==Error::None && good.header.calibrationTurns==4);
  CHECK(good.header.calibratedTurnQ16==8152UL*65536+16384);
  const uint32_t fixed=8170UL*65536+32768;
  auto diagnostic=recordCalibration({500,8652,16805,24957,33109},Result::Complete,fixed);
  Settings effective;CHECK(decodeSettings(diagnostic.header.settings,sizeof(diagnostic.header.settings),effective));
  CHECK(effective.calibrated && effective.turnQ16==fixed);
  CHECK(diagnostic.header.calibratedTurnQ16==8152UL*65536+16384);
  auto bad=recordCalibration({500,8652,13652},Result::Fault);
  CHECK(bad.header.error==Error::CalibrationFailed && bad.header.calibrationTurns==1);
  auto interrupted=recordCalibration({500},Result::Aborted);
  CHECK(interrupted.header.error==Error::Aborted && !interrupted.header.calibrationTurns);
  const auto time=good.header.startMs;
  for(unsigned i=1;i<=7;++i){
    auto report=i==6?interrupted:(i==5?bad:good);
    report.header.startMs=time+i;
    CHECK(saveCalibration(report));
    auto game=makeReport(100+i);CHECK(save(game));
  }
  CHECK(mount() && calibrationsStored()==4);checkRanks(7,4);
  auto checkCal=[&](){
    CalibrationReport restored;
    for(unsigned rank=1;rank<=4;++rank) {
      CHECK(loadCalibrationForExport(rank,nullptr,restored));
      const unsigned seq=8-rank;
      const auto& original=seq==6?interrupted:(seq==5?bad:good);
      CHECK(restored.header.startMs==uint32_t(time+seq) && restored.header.sequence==seq);
      CHECK(restored.header.calibratedTurnQ16==original.header.calibratedTurnQ16);
      CHECK(restored.count==original.count && restored.header.result==original.header.result);
      CHECK(std::memcmp(original.samples,restored.samples,sizeof(original.samples))==0);
    }
  };
  checkCal();
  ++cases;
  // Rotating the general history cannot evict the separate calibration history.
  for(unsigned i=8;i<=15;++i){auto game=makeReport(100+i);CHECK(save(game));}
  CHECK(mount());checkRanks(15,4);checkCal();
  ++cases;
  testfs::writeBudget=sizeof(CalibrationReport)+1;
  CHECK(!saveCalibration(interrupted));
  CHECK(std::string(calibrationStorageState())=="write-failed-RAM-only");
  CalibrationReport out;
  CHECK(loadCalibrationForExport(1,&interrupted,out) && out.header.result==Result::Aborted);
  CHECK(loadCalibrationForExport(2,&interrupted,out) && out.header.sequence==7);
  CHECK(!loadCalibrationForExport(0,&interrupted,out) && !loadCalibrationForExport(5,nullptr,out));
  CHECK(mount());checkCal();
  ++cases;
  auto& bytes=testfs::files.at("/dealer-cal-1"); // Sequence 7 after 5 physical slots.
  CHECK(bytes.size()==sizeof(CalibrationReport)+sizeof(uint32_t));bytes.back()^=0x80;
  CHECK(mount() && calibrationsStored()==3);
  CHECK(loadCalibrationForExport(1,nullptr,out) && out.header.sequence==6);
  checkRanks(15,4);
  auto invalid=good;invalid.count=6;
  CHECK(!saveCalibration(invalid));
  invalid.count=0;invalid.header.kind=Kind::Deal;CHECK(!saveCalibration(invalid));
}
int main() {
  recordCards();recordPartial();recordUnexpectedExit();legacyArchive();ringAndPowerLoss();ramFallback();calibrationArchive();
  std::printf("PASS flight log: %u cases, %u checks\n",cases,checks);
}
