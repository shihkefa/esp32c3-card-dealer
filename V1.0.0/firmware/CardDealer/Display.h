#pragma once
#include <Arduino.h>
#include <Wire.h>
#include "DealerCore.h"

class DealerDisplay {
 public:
  bool begin();
  bool busy() const {return sending_;}
  bool ready() const {return ready_;}
  bool service(); // at most one bounded 16-byte I2C data transaction
  void compose(const dealer::Controller& c,uint8_t field,bool advanced,uint8_t advancedField,const char* notice=nullptr);
 private:
  uint8_t frame_[1024]{};
  bool ready_=false,sending_=false,needPage_=true;
  uint16_t offset_=0;
  bool commands(const uint8_t* bytes,size_t count);
  void text(int x,int y,const char* utf8);
  void pixel(int x,int y);
};
