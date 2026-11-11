#include "Display.h"
#include "BoardConfig.h"
#include "Font16.h"
#include <stdio.h>
#include <string.h>

bool DealerDisplay::commands(const uint8_t* data,size_t n) {
  Wire.beginTransmission(Board::kOledAddress);Wire.write(uint8_t(0));Wire.write(data,n);
  return Wire.endTransmission()==0;
}
bool DealerDisplay::begin() {
  // SSD1306 128x64, internal charge pump, page addressing.
  const uint8_t init[]={0xAE,0xD5,0x80,0xA8,0x3F,0xD3,0,0x40,0x8D,0x14,
    0x20,0x02,0xA1,0xC8,0xDA,0x12,0x81,0x8F,0xD9,0xF1,0xDB,0x20,0xA4,0xA6,0xAF};
  ready_=commands(init,sizeof(init));sending_=false;offset_=0;needPage_=true;
  return ready_;
}
void DealerDisplay::pixel(int x,int y) {
  if(x>=0&&x<128&&y>=0&&y<64)frame_[(y/8)*128+x]|=uint8_t(1U<<(y&7));
}
static uint32_t nextCodepoint(const char*& s) {
  const uint8_t a=uint8_t(*s++);
  if(a<128)return a;
  if((a&0xE0)==0xC0 && s[0]){uint32_t r=((a&31)<<6)|(uint8_t(s[0])&63);s+=1;return r;}
  if((a&0xF0)==0xE0 && s[0]&&s[1]){uint32_t r=((a&15)<<12)|((uint8_t(s[0])&63)<<6)|(uint8_t(s[1])&63);s+=2;return r;}
  return '?';
}
void DealerDisplay::text(int x,int y,const char* s) {
  while(*s && x<128) {
    uint32_t cp=nextCodepoint(s);
    if(cp>=32 && cp<127) {
      for(uint8_t r=0;r<16;++r){uint8_t b=pgm_read_byte(&kAscii16[cp-32][r]);for(uint8_t col=0;col<8;++col)if(b&(0x80>>col))pixel(x+col,y+r);}
      x+=8;continue;
    }
    int lo=0,hi=int(kCjkCount)-1,found=-1;
    while(lo<=hi){int m=(lo+hi)/2;uint16_t c=pgm_read_word(&kCjkCodes[m]);if(c==cp){found=m;break;}if(c<cp)lo=m+1;else hi=m-1;}
    if(found>=0) {for(uint8_t r=0;r<16;++r)for(uint8_t col=0;col<16;++col)
      if(pgm_read_byte(&kCjk16[found][r*2+col/8])&(0x80>>(col&7)))pixel(x+col,y+r);}
    else {text(x,y,"?");}
    x+=16;
  }
}
static const char* profileName(dealer::Profile p) {
  switch(p){case dealer::Profile::Landlord:return "鬥地主";case dealer::Profile::Guandan:return "摜蛋";
    case dealer::Profile::Four13:return "四人十三";case dealer::Profile::Three13:return "三人十三";default:return "自訂";}
}
static const char* faultText(dealer::Error e) {
  using dealer::Error;
  switch(e){
    case Error::InvalidSettings:return "設定超出範圍";case Error::NeedCalibration:return "請先校正圈數";
    case Error::OutletBlocked:return "請清空出牌口";case Error::NoCard:return "無牌或取牌失敗";
    case Error::CardStuck:return "卡牌請清出口";case Error::UnexpectedCard:return "非預期出牌";
    case Error::HomeMissing:return "參考感測未觸發";case Error::HomeMismatch:return "轉向參考不符";
    case Error::IoFault:return "輸入輸出異常";case Error::SensorOverflow:return "出口訊號過多";
    case Error::MotionFault:return "旋轉動作異常";case Error::CalibrationFailed:return "圈數校正失敗";
    case Error::Aborted:return "已中止請重排";default:return "未知錯誤";
  }
}
void DealerDisplay::compose(const dealer::Controller& c,uint8_t field,bool advanced,uint8_t af,const char* notice) {
  if(!ready_||sending_)return;
  memset(frame_,0,sizeof(frame_));char line[80];const dealer::Settings& s=c.settings();
  using dealer::Stage;
  if(c.stage()==Stage::Fault) {
    snprintf(line,sizeof(line),"故障 E%02u",unsigned(c.error()));text(0,0,line);
    text(0,16,faultText(c.error()));text(0,32,"清牌後按開始");text(0,48,"重置後再發牌");
  } else if(c.stage()==Stage::Calibrating) {
    snprintf(line,sizeof(line),"校正 %u/4",c.calibrationTurns());text(0,0,line);
    text(0,16,"請先清空牌倉");text(0,32,"約需一至二分");text(0,48,"開始鍵可取消");
  } else if(advanced && !c.active()) {
    const char* labels[]={"遊戲模式","圈數校正","取牌PWM","出牌PWM","轉向速度","返回"};
    text(0,0,labels[af%6]);
    switch(af%6){
      case 0:text(0,20,profileName(s.profile));break;
      case 1:text(0,20,"按開始啟動");break;
      case 2:snprintf(line,sizeof(line),"%u /255",s.feedPwm);text(0,20,line);break;
      case 3:snprintf(line,sizeof(line),"%u /255",s.ejectPwm);text(0,20,line);break;
      case 4:snprintf(line,sizeof(line),"%u step/s",s.maxStepRate);text(0,20,line);break;
      default:text(0,20,"按開始返回");break;
    }
    text(0,48,"SET換項 RUN確認");
  } else {
    const char* title=profileName(s.profile);
    if(c.stage()==Stage::Positioning)title="旋轉";
    else if(c.stage()==Stage::Paused)title="已暫停";
    else if(c.stage()==Stage::Complete)title="已完成";
    else if(c.active())title=c.pauseRequested()?"待暫停":"發牌";
    if(!s.calibrated && c.stage()==Stage::Idle)title="需校正";
    snprintf(line,sizeof(line),"%s %u/%u",title,c.done(),dealer::totalCards(s));
    text(0,0,notice?notice:line);
    const bool editable=c.stage()==Stage::Idle||c.stage()==Stage::Complete;
    snprintf(line,sizeof(line),"每人張數 %u",s.cards);text(0,16,editable&&field==0?">":" ");text(10,16,line);
    snprintf(line,sizeof(line),"玩家人數 %u",s.players);text(0,32,editable&&field==1?">":" ");text(10,32,line);
    snprintf(line,sizeof(line),"餘牌張數 %u",s.remainder);text(0,48,editable&&field==2?">":" ");text(10,48,line);
  }
  offset_=0;needPage_=true;sending_=true;
}
bool DealerDisplay::service() {
  if(!ready_)return false;
  if(!sending_)return true;
  if(needPage_) {
    uint8_t cmd[]={uint8_t(0xB0+offset_/128),0x00,0x10};
    if(!commands(cmd,sizeof(cmd))){ready_=false;return false;}
    needPage_=false;return true;
  }
  Wire.beginTransmission(Board::kOledAddress);Wire.write(uint8_t(0x40));
  Wire.write(frame_+offset_,16);
  if(Wire.endTransmission()!=0){ready_=false;return false;}
  offset_+=16;
  if(offset_>=sizeof(frame_))sending_=false;
  else if((offset_%128)==0)needPage_=true;
  return true;
}
