#pragma once
#include "DealerCore.h"

namespace flight {
constexpr unsigned kSlots=4;
constexpr uint32_t kLegacyLogMagic=0x31474C44;
enum class Kind:uint8_t {Deal,Calibration,IdleFault};
enum class Result:uint8_t {Complete,Fault,Aborted,Rejected};

// All positions are commanded half-steps. Negative-one timestamps mean unavailable.
struct Card {
  int32_t spinMs=-1,feedMs=-1,blockedMs=-1,clearMs=-1,countMs=-1;
  int32_t target=0,blockedPosition=0,clearPosition=0,phaseError=0;
  uint16_t releaseMs=0;
  uint8_t player=0,qualifiedEdges=0; // Player zero is the remainder position.
};
struct Header {
  uint32_t magic=0x32474C44,sequence=0,startMs=0,elapsedMs=0;
  int32_t origin=0,stopPosition=0,homePosition=0,homeTravel=0;
  int32_t finalTarget=0,finalPhaseError=0;
  uint32_t rawEdges=0,qualifiedEdges=0,overflows=0;
  uint16_t rowCount=0,regularDone=0,extraDone=0,homePulses=0;
  uint8_t settings[dealer::kSettingsBytes]{};
  Kind kind=Kind::Deal;
  Result result=Result::Complete;
  dealer::Error error=dealer::Error::None;
  dealer::Stage faultStage=dealer::Stage::Idle;
  dealer::HomeFault homeFault=dealer::HomeFault::None;
  uint8_t exitBlocked=0,homeBlocked=0;
  uint8_t calibrationTurns=0;
  uint32_t calibratedTurnQ16=0;
  uint32_t unexpectedCount=0;
  dealer::Stage unexpectedLastStage=dealer::Stage::Idle;
};
struct Report {Header header; Card rows[dealer::kCapacity];};
struct CalSample {int32_t position=0;uint32_t elapsedMs=0;};
struct CalibrationReport {Header header;uint8_t count=0;CalSample samples[5];};
struct Counters {uint32_t raw,qualified,overflows;};
class Recorder {
 public:
  Report report;
  CalibrationReport calibration;
  bool recording=false;
  void begin(Kind kind,const dealer::Settings& s,uint32_t ms,int32_t position,Counters counters,bool homeBlocked=false);
  void stage(const dealer::Controller& c,uint32_t ms);
  void edge(const dealer::Controller& c,bool blocked,uint32_t us,uint32_t ms,int32_t position);
  void finish(const dealer::Controller& c,Result result,uint32_t ms,int32_t position,Counters counters);
 private:
  bool previousHome_=false;
  Counters initial_{};
  Card* current(const dealer::Controller& c);
};

// Only called during boot or with all motor outputs stopped.
bool mount();
bool save(Report& report);
bool load(unsigned newestFirst,Report& result);
bool loadForExport(unsigned rank,const Report* ramLatest,Report& result);
unsigned stored();
const char* storageState();
bool saveCalibration(CalibrationReport& report);
bool loadCalibrationForExport(unsigned rank,const CalibrationReport* ramLatest,CalibrationReport& result);
unsigned calibrationsStored();
const char* calibrationStorageState();
}
