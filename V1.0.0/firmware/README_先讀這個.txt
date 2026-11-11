撲克牌發牌機韌體 V1.0.0
適用：ESP32-C3 SuperMini 原生USB板；CAD V1.0.0、28BYJ-48 5V、30T帶60T。

打開 CardDealer/CardDealer.ino 即可使用 Arduino IDE 編譯；不需另外安裝OLED、PCF或步進馬達函式庫。
使用 Espressif 的 esp32 3.x 核心。本次實際編譯版本、Flash/RAM與測試結果見 verification.json / docs/建置與驗證結果.txt。
附上的 Font16.h 是已產生的中文字形點陣，平常燒錄不需要Python或字型產生器。

功能：
－OLED中文顯示每人張數、玩家人數、餘牌張數，及進度/暫停/故障。
－鬥地主、摜蛋、四人13張、三人13張四種預設，以及自訂參數。
－第一張保持當前朝向；3人每張120°、4人每張90°；餘牌在第一和第二位之間。
－四按鍵操作、長按調整/中止、設定與圈數校正保存至NVS。
－硬體計時器驅動步進；螢幕分段刷新，避免I2C長交易打亂步進。
－出口完整遮光/透光週期計數；無牌/卡牌/非預期出牌/參考不符/I2C錯誤停機。
－USB序列診斷、限時馬達點動；每次開機明確停止並卸載Wi-Fi驅動、停止藍牙控制器。
－全程使用本機按鍵與螢幕；不會自動連網或開啟藍牙，USB status可確認wifi_off / ble_off。

開始之前：
1. 依 docs/GPIO接線表.csv 和 docs/滑環12路接線.csv 接線；詳細供電見 docs/接線與供電.txt。
2. 本版確定採 GPIO21=SDA、GPIO20=SCL。不是常見的8/9，也不是UART0。
3. 旋轉參考接 PCF8574 P4，透過第10路滑環；出口感測直接接GPIO10。
   12路滑環現用10路，餘2路；以本套接線表為準。
4. 開發板USB燒錄口與機殼TP4056充電口不同。USB接電腦前先斷開ESP 5V分支跳線/接頭，GND仍共地。
   詳見 docs/接線與供電.txt；不是只把電池總開關關掉就完成USB供電隔離。
5. Arduino IDE：ESP32C3 Dev Module；USB CDC On Boot=Enabled；Flash Mode=DIO；Flash Size=4MB。
6. 首次運轉先空牌倉、測感測器與馬達方向。長按SET約1秒，停在「圈數校正」，短按RUN開始。
7. 校正約1至2分鐘，會取得4個完整參考週期。完成後，將整台機器面向第一位玩家，再放牌並按RUN。

按鍵與模式操作見 docs/使用與首次測試.txt；故障碼和序列命令見 docs/診斷與故障碼.txt。
無線關閉與省電範圍見 docs/省電與無線功能.txt。

現有28BYJ-48搭配2:1減速，逐張轉90/120°所需時間較長，本韌體不能讓整機保證每秒2至4張。
本套已做程式編譯與主機端模擬；沒有實際燒錄到你的板子、實體送牌或電源測試。
單一出口光電無法可靠分辨完全重疊的雙張牌，仍須調好分牌閘和摩擦墊。
發生故障或中止後不續發當局；清牌並重新整理整副牌，再開始。沒有斷電續發。

原始碼結構：
CardDealer.ino：GPIO/PWM/中斷、按鍵、USB指令、NVS與主迴圈。
BoardConfig.h：接腳、感測極性、I2C地址與旋轉電氣方向。
RadioPower.h：開機關閉Wi-Fi/BLE，以及USB診斷的實際控制器狀態查詢。
DealerCore.h/.cpp：與Arduino無關的發牌/校正/故障狀態機和設定序列化。
StepperPlan.h：100微秒整數步進排程。
Display.h/.cpp、Font16.h：SSD1306頁模式與中文點陣；不是SH1106驅動。
tests/core_tests.cpp：直接執行上述核心和排程器的模擬測試。
tools/Build-Arduino.ps1：可選的CLI編譯腳本；只編譯，不會自動燒錄。
bin/：本次已編譯二進位；請優先用Arduino IDE從原始碼上傳。
