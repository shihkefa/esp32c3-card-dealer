V1.0.0 來源與重建

韌體：
Arduino IDE使用Espressif esp32核心3.x，本包實際編譯3.0.5。
打開firmware/CardDealer/CardDealer.ino，Board選ESP32C3 Dev Module，
USB CDC On Boot開啟、Flash Mode DIO、4MB。也可用firmware/tools/Build-Arduino.ps1。
修改程式後重新編譯；根目錄的整合燒錄檔是本次交付檔，不會隨原始碼修改而自動更新。

機構：
3d/source/requirements.txt列出Python依賴。安裝後執行build_cad.py可重新匯出模型與預覽。
參數在design_params.json，零件細節在build_cad.py；輸出固定到本專案3d/。
virtual_assembly_check.py、check_fasteners.py及validate_cad.py檢查參考包絡與匯出模型。
check_p02_split.py及check_p04_split.py核對分件列印面、插入路徑與螺母/工具間隙。
P04B齒頂與接合面Z43.5mm、齒底Z36mm；P04A與P02A頂圈名義間隙2.0mm。
只變更P04B與P26原生列印幾何，其餘38種STL保持不變。P04A與整個上半部裝配抬高1.5mm；下方軸頸、軸承肩、P06、滑環與P05保持原位。
P26薄片向下延長1.5mm，原生最低Z34.1mm，裝配最低Z35.6mm；P25與光電高度保持不變。
組裝匯出與示意圖應使用assembly_pose(pid, shape)及inclined_head_pose(shape)，不得把抬高量烘焙進所有零件STL，亦不得讓傾斜後座標重複旋轉或抬高。
check_p05_fasteners.py核對P05A/P05B分件裝入、完整錐座/閉孔、螺母捕捉及包含P02A的L型工具入場、轉動與換位。
P05B平面版需同時核對Y−10.5貼床平面、45°削角及移到平面上的編號；列印姿態(90,0,0)與組裝姿態分別保存。
P05A平口配合版需核對內腔Y−10.7平面與P05B的Y−10.5平口之0.2mm名義側隙；外圈30齒、固定孔及防脫裙邊不得改動。
export_assembled_stl.py匯出整機觀看用STL，render_numbering.py產生凹刻編號核對圖。
render_p02_split.py及render_p04_split.py產生分件組裝與列印方向圖。
render_p05_fasteners.py產生P05A/P05B分件、閉合夾座與先鎖軸再裝齒輪的裝配圖。
P05B_平面貼床與削角.png說明新列印平面與削角；D孔、圓孔及螺母槽的小橋接仍需切片確認。
P05A_P05B_平口配合.png說明齒輪內部D形避空與夾座平口的位置及名義側隙；P05B可沿用本包平面版。
模型預覽目前使用Windows微軟正黑體，換平台需調整字型路徑。

接線圖：
source/pictorial/build_pictorial.py產生wiring/內的HTML、SVG、兩份PDF、PNG與接腳清單。
使用Python、ReportLab、pypdf、Pillow、Poppler pdftoppm及Windows字型。
source/wiring/render_helpers.py提供共用繪圖與GPIO核對。
source/wiring/logical_nets.json為指定板型的電氣端點；routes-cache.json只快取走線。
更改板型或接腳必須重新核對實物，不能只更改文字標籤。

BOM：
source/bom/build_bom.mjs使用@oai/artifact-tool及本機Codex附帶Node/Python工具。
讀取3d/parts_manifest.json及fastener_catalog.json，再輸出本版BOM與核對預覽。
執行前將node_modules連結到已安裝的artifact-tool套件目錄，完成後移除連結。
attach_links.py只附加Excel原生超連結，資料、公式及排版由artifact-tool產生。

封裝：
網頁組裝手冊：source/manual/assembly_steps.json編寫22步，render_manual.py依現有CAD產生manual/assets/示意圖；不重匯STL。
build_manual.py把步驟、零件、五金、圖片及原互動接線圖全部嵌入單一HTML。
export_manual_3d.py以現有CAD三角面匯出獨立部件、明確螺絲軸線與每步場景至manual/assets/assembly_3d.json，不修改STL。
viewer3d.js/css處理旋轉、縮放、選取、隱藏及分解；integrate3d.js將3D與原步驟及示意圖切換整合。
Three.js固定0.180.0，從https://registry.npmjs.org/three/-/three-0.180.0.tgz下載並解到.build/web3d/three/package。
打包工具esbuild-wasm固定0.25.10，從https://registry.npmjs.org/esbuild-wasm/-/esbuild-wasm-0.25.10.tgz解到.build/web3d/esbuild-wasm/package。
保留下載的three.tgz，使用bundle_3d.mjs產生manual/vendor/three-orbit.min.js、MIT授權及雜湊；平常閱讀無需以上工具。
3D資料及本地JS/CSS由build_manual.py一併嵌入HTML，不使用外部CDN或fetch。
verify_manual.mjs以Codex附帶Node與Playwright在獨立headless Chrome檢查離線、完成勾選、搜尋、放大、接線互動及手機寬度；截圖暫存在.build/manual-qa。
verify_manual_3d.mjs另外檢查實際WebGL渲染、拖曳、縮放、分解、點選、手機手勢及無WebGL的圖解回退；截圖暫存在.build/manual-3d-qa。
該手冊不用伺服器、CDN或網路。重建需Python Pillow；重畫CAD圖或重匯出3D另需3d/source/requirements.txt。

source/package_project.py核對成品檔案、更新SHA-256並在專案旁建立完整ZIP。
重建若更改幾何、電路或狀態機，需重跑受影響的驗證，不可直接沿用既有紀錄。

上殼分件：P32A包覆邊與P32B的1.5mm退台由同一CAD來源生成，原上罩孔位與四組內連接不移動。
check_p32_split.py核對包覆、0.3mm名義間隙、分件裝入與內側連接；P32_台階包覆與接縫.png供手冊step17細節對照，先產生本圖再執行build_manual.py。
P32_內側接合與列印方向.png按目前模型重繪；P32_居中與分件組裝.png只保留前一階段居中的歷史比較，不當作本版台階外觀。
render_p32_overlap.py產生上殼組合外觀及接縫局部四倍放大；render_p32_split.py重繪內側接合，並保留已有居中歷史比較圖。
手冊數量由parts_manifest與fastener_catalog填入，零件、五金與模型場景數量維持一致。
P04B/P26幾何更新後，需重新輸出所有含上半部的整機圖、P04詳圖與手冊3D場景，再執行render_manual.py及build_manual.py；不可只改步驟文字而沿用原高度圖片。
