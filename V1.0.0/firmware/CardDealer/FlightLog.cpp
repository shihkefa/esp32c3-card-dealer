#include "FlightLog.h"
#include <SPIFFS.h>
#include <esp_partition.h>
#include <esp_rom_crc.h>
#include <stddef.h>

namespace flight {
void Recorder::begin(Kind kind,const dealer::Settings& s,uint32_t ms,int32_t position,Counters counters,bool homeBlocked) {
  report.header=Header{};
  report.header.kind=kind;report.header.startMs=ms;report.header.origin=position;
  dealer::encodeSettings(s,report.header.settings);
  initial_=counters;previousHome_=homeBlocked;recording=true;
}
Card* Recorder::current(const dealer::Controller& c) {
  const unsigned i=c.done();
  if(report.header.kind!=Kind::Deal || i>=dealer::totalCards(c.settings()) || i>=dealer::kCapacity)return nullptr;
  if(i==report.header.rowCount) {
    Card& row=report.rows[i];row=Card{};row.target=c.target();
    row.player=i<unsigned(c.settings().players)*c.settings().cards ? 1+i%c.settings().players : 0;
    ++report.header.rowCount;
  }
  return i<report.header.rowCount ? &report.rows[i] : nullptr;
}
void Recorder::stage(const dealer::Controller& c,uint32_t ms) {
  if(!recording)return;
  auto& h=report.header;
  if(!previousHome_ && c.homeBlocked())++h.homePulses;
  previousHome_=c.homeBlocked();
  if(h.kind!=Kind::Deal)return;
  const int32_t dt=int32_t(ms-h.startMs);
  if(c.done()>h.regularDone+h.extraDone && c.done()<=h.rowCount) {
    Card& row=report.rows[c.done()-1];row.countMs=dt;
    row.phaseError=c.phaseErrorSteps();row.releaseMs=c.measuredReleaseMs();
  }
  h.regularDone=c.regularDone();h.extraDone=c.remainderDone();
  if(c.stage()==dealer::Stage::SpinUp || c.stage()==dealer::Stage::Feeding) {
    Card* row=current(c);if(!row)return;
    row->target=c.target();
    if(c.stage()==dealer::Stage::SpinUp && row->spinMs<0)row->spinMs=dt;
    if(c.stage()==dealer::Stage::Feeding && row->feedMs<0)row->feedMs=dt;
  }
}
void Recorder::edge(const dealer::Controller& c,bool blocked,uint32_t us,uint32_t ms,int32_t position) {
  if(!recording)return;
  // Run totals retain every qualified edge. Only an accepted card pulse
  // belongs in the current player's release timing.
  if(c.exitBlocked()==blocked || (blocked ? !c.expectsExitBlock(us) : c.stage()!=dealer::Stage::Exiting))return;
  Card* row=current(c);if(!row)return;
  if(row->qualifiedEdges<255)++row->qualifiedEdges;
  const int32_t dt=int32_t(ms-report.header.startMs);
  if(blocked && row->blockedMs<0){row->blockedMs=dt;row->blockedPosition=position;}
  if(!blocked && row->clearMs<0){row->clearMs=dt;row->clearPosition=position;}
}
void Recorder::finish(const dealer::Controller& c,Result result,uint32_t ms,int32_t pos,Counters counts) {
  stage(c,ms);
  auto& h=report.header;
  h.result=result;h.error=c.error();h.faultStage=c.faultStage();h.homeFault=c.homeFault().cause;
  if(h.kind!=Kind::IdleFault) {
    h.unexpectedCount=c.unexpectedExit().count;
    h.unexpectedLastStage=c.unexpectedExit().lastStage;
  }
  h.finalTarget=c.target();h.finalPhaseError=c.phaseErrorSteps();
  if(h.kind==Kind::Deal && h.error==dealer::Error::ReleaseWindow && c.done()<h.rowCount){
    Card& row=report.rows[c.done()];row.phaseError=c.phaseErrorSteps();
    if(row.clearMs>=0)row.releaseMs=c.measuredReleaseMs();
  }
  h.stopPosition=pos;h.homePosition=c.homeFault().position;h.homeTravel=c.homeFault().travel;
  h.exitBlocked=c.exitBlocked();h.homeBlocked=c.homeBlocked();h.calibrationTurns=c.calibrationTurns();
  h.calibratedTurnQ16=c.settings().turnQ16;h.elapsedMs=ms-h.startMs;
  h.rawEdges=counts.raw-initial_.raw;h.qualifiedEdges=counts.qualified-initial_.qualified;
  h.overflows=counts.overflows-initial_.overflows;recording=false;
  if(h.kind==Kind::Calibration){
    const auto& trace=c.calibrationTrace();
    if(result==Result::Complete && h.error==dealer::Error::None && trace.count==dealer::kCalibrationSamples)
      h.calibratedTurnQ16=trace.completeMeanQ16();
    calibration=CalibrationReport{};calibration.header=h;
    static_assert(dealer::kCalibrationSamples==5,"Calibration log layout must match controller");
    calibration.count=trace.count<dealer::kCalibrationSamples?trace.count:dealer::kCalibrationSamples;
    for(uint8_t i=0;i<calibration.count;++i){
      calibration.samples[i].position=trace.samples[i].position;
      calibration.samples[i].elapsedMs=trace.samples[i].ms-h.startMs;
    }
  }
}

// The extra physical slot lets a torn write leave all four visible runs intact.
constexpr unsigned kPhysicalSlots=kSlots+1;
static bool mounted=false;
static_assert(offsetof(Report,rows)==sizeof(Header),"Log binary header layout");
constexpr size_t kLegacyHeaderBytes=offsetof(Header,unexpectedCount);
static_assert(kLegacyHeaderBytes==104,"Keep the on-device DLG1 header layout");
static size_t byteSize(const Header& h,const Report*){return sizeof(Header)+sizeof(Card)*h.rowCount;}
static size_t byteSize(const Header&,const CalibrationReport*){return sizeof(CalibrationReport);}
template<typename Record>
class Archive {
 public:
  explicit Archive(const char* const (&slotPaths)[kPhysicalSlots]):paths(slotPaths){}
  void scan();
  unsigned stored() const;
  const char* storage="not-mounted";
  bool save(Record& report);
  bool load(unsigned rank,Record& result);
  bool exportRank(unsigned rank,const Record* ramLatest,Record& result);
 private:
  const char* const (&paths)[kPhysicalSlots];
  uint32_t ids[kPhysicalSlots]{},latestId=0;
  bool validate(unsigned slot,Record* dst,uint32_t& seq);
};
template<typename Record> bool Archive<Record>::validate(unsigned slot,Record* dst,uint32_t& seq) {
  if(!SPIFFS.exists(paths[slot]))return false;
  File file=SPIFFS.open(paths[slot],FILE_READ);if(!file)return false;
  Header h{};
  auto* headerBytes=reinterpret_cast<uint8_t*>(&h);
  if(file.read(headerBytes,kLegacyHeaderBytes)!=kLegacyHeaderBytes)return false;
  const size_t diskHeaderSize=h.magic==kLegacyLogMagic?kLegacyHeaderBytes:sizeof(Header);
  if(h.magic!=kLegacyLogMagic && h.magic!=Header{}.magic)return false;
  if(diskHeaderSize>kLegacyHeaderBytes &&
     file.read(headerBytes+kLegacyHeaderBytes,diskHeaderSize-kLegacyHeaderBytes)!=diskHeaderSize-kLegacyHeaderBytes)return false;
  const size_t payloadSize=byteSize(h,dst)-sizeof(Header);
  if(unsigned(h.result)>unsigned(Result::Rejected) || unsigned(h.kind)>unsigned(Kind::IdleFault) ||
     !h.sequence || h.rowCount>dealer::kCapacity || file.size()!=diskHeaderSize+payloadSize+sizeof(uint32_t))return false;
  if(dst)dst->header=h;
  uint32_t crc=esp_rom_crc32_le(0,headerBytes,diskHeaderSize);
  uint8_t chunk[256];
  size_t offset=sizeof(Header),remaining=payloadSize;
  while(remaining) {
    size_t n=remaining<sizeof(chunk)?remaining:sizeof(chunk);
    uint8_t* block=dst?((uint8_t*)dst)+offset:chunk;
    if(file.read(block,n)!=n)return false;
    crc=esp_rom_crc32_le(crc,block,n);offset+=n;remaining-=n;
  }
  uint32_t expected=0;
  if(file.read((uint8_t*)&expected,sizeof(expected))!=sizeof(expected)||crc!=expected)return false;
  seq=h.sequence;return true;
}
static bool entirelyBlank() {
  const esp_partition_t* p=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_SPIFFS,"spiffs");
  if(!p)return false;
  uint32_t block[128];
  for(size_t at=0;at<p->size;at+=sizeof(block)){
    if(esp_partition_read(p,at,block,sizeof(block))!=ESP_OK)return false;
    for(uint32_t value:block)if(value!=UINT32_MAX)return false;
  }
  return true;
}
template<typename Record> void Archive<Record>::scan(){
  latestId=0;for(uint32_t& id:ids)id=0;
  if(!mounted){storage="unavailable-RAM-only";return;}
  for(unsigned i=0;i<kPhysicalSlots;++i)
    if(validate(i,nullptr,ids[i]) && (!latestId || int32_t(ids[i]-latestId)>0))latestId=ids[i];
  storage="ready";
}
template<typename Record> unsigned Archive<Record>::stored() const {unsigned n=0;for(uint32_t id:ids)if(id)++n;return n<kSlots?n:kSlots;}
template<typename Record> bool Archive<Record>::save(Record& report){
  if(!mounted || report.header.rowCount>dealer::kCapacity)return false;
  unsigned slot=0;
  for(unsigned i=0;i<kPhysicalSlots;++i){
    if(!ids[i]){slot=i;break;}
    if(uint32_t(latestId-ids[i])>uint32_t(latestId-ids[slot]))slot=i;
  }
  uint32_t next=latestId+1;if(!next)next=1;
  report.header.sequence=next;
  const uint8_t* bytes=(const uint8_t*)&report;
  size_t n=byteSize(report.header,&report);
  uint32_t crc=esp_rom_crc32_le(0,bytes,n);
  File f=SPIFFS.open(paths[slot],FILE_WRITE);
  if(!f){storage="write-failed-RAM-only";return false;}
  ids[slot]=0;
  bool ok=f.write(bytes,n)==n && f.write((const uint8_t*)&crc,sizeof(crc))==sizeof(crc);
  f.close();
  if(!ok || !validate(slot,nullptr,ids[slot]) || ids[slot]!=next){storage="write-failed-RAM-only";return false;}
  latestId=next;storage="ready";return true;
}
template<typename Record> bool Archive<Record>::load(unsigned rank,Record& result) {
  if(!mounted || !rank || rank>stored())return false;
  int choice=-1;
  for(unsigned i=0;i<kPhysicalSlots;++i)if(ids[i]){
    unsigned newer=0;
    for(uint32_t other:ids)if(other && int32_t(other-ids[i])>0)++newer;
    if(newer+1==rank){choice=int(i);break;}
  }
  uint32_t seq=0;return choice>=0&&validate(unsigned(choice),&result,seq);
}
template<typename Record> bool Archive<Record>::exportRank(unsigned rank,const Record* ramLatest,Record& result){
  if(rank<1 || rank>kSlots)return false;
  if(ramLatest && rank==1){result=*ramLatest;return true;}
  return load(rank-unsigned(ramLatest!=nullptr),result);
}
static const char* const dealPaths[kPhysicalSlots]={"/dealer-flight-0","/dealer-flight-1","/dealer-flight-2","/dealer-flight-3","/dealer-flight-4"};
static const char* const calPaths[kPhysicalSlots]={"/dealer-cal-0","/dealer-cal-1","/dealer-cal-2","/dealer-cal-3","/dealer-cal-4"};
static Archive<Report> dealArchive(dealPaths);
static Archive<CalibrationReport> calArchive(calPaths);
bool mount(){
  // Never format a populated partition that happens to fail mounting.
  mounted=SPIFFS.begin(false) || (entirelyBlank() && SPIFFS.begin(true));
  dealArchive.scan();calArchive.scan();return mounted;
}
unsigned stored(){return dealArchive.stored();}
unsigned calibrationsStored(){return calArchive.stored();}
const char* storageState(){return dealArchive.storage;}
const char* calibrationStorageState(){return calArchive.storage;}
bool save(Report& report){return dealArchive.save(report);}
bool saveCalibration(CalibrationReport& report){
  return report.count<=5 && report.header.kind==Kind::Calibration && calArchive.save(report);
}
bool load(unsigned rank,Report& result){return dealArchive.load(rank,result);}
bool loadForExport(unsigned rank,const Report* ramLatest,Report& result){return dealArchive.exportRank(rank,ramLatest,result);}
bool loadCalibrationForExport(unsigned rank,const CalibrationReport* ramLatest,CalibrationReport& result){
  return calArchive.exportRank(rank,ramLatest,result) && result.count<=5 && result.header.kind==Kind::Calibration;
}
}
