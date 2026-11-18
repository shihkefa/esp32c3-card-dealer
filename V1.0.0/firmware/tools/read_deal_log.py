"""Read finished card-dealer reports over native USB CDC. Requires pyserial."""
import argparse
import csv
import re
import sys
import time
from pathlib import Path


def select_port(ports):
    # Espressif's USB Serial/JTAG interface is shared by several chips. Verify
    # the dealer's log-status reply on the selected port before requesting data.
    matches = [p.device for p in ports if (p.vid, p.pid) == (0x303A, 0x1001)]
    if len(matches) != 1:
        raise ValueError("請以 --port 指定發牌機的序列埠。自動偵測結果為 "
                         + (", ".join(matches) if matches else "無相符的原生 USB 序列埠"))
    return matches[0]


def read_lines(port, deadline, idle_seconds):
    pending = bytearray()
    idle_deadline = time.monotonic() + idle_seconds
    while time.monotonic() < min(deadline, idle_deadline):
        data = port.read(max(1, min(port.in_waiting, 2048)))
        if not data:
            continue
        idle_deadline = time.monotonic() + idle_seconds
        pending.extend(data)
        while b'\n' in pending:
            line, _, pending = pending.partition(b'\n')
            yield line.rstrip(b'\r').decode('utf-8', errors='replace')
        if len(pending) > 4096:
            raise ValueError("序列資料的一行過長，請確認已選到發牌機。")


def read_status(port, timeout, calibration=False):
    command = 'cal' if calibration else 'log'
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        port.write(f'{command} status\n'.encode('ascii'))
        # On first power-up the serial device can enumerate before the sketch
        # finishes starting. Only the read-only status query is retried.
        for line in read_lines(port, min(deadline, time.monotonic() + 1.2), 1.2):
            if re.fullmatch(command.upper() + r' storage=\S+ stored=\d+/4 recording=[01] ram_latest=[01] export=[01]', line):
                return line
            if line.startswith('ERROR COMMAND'):
                raise ValueError(f"這版韌體未提供 {command} 指令。")
    raise ValueError(f"等待發牌機回覆 {command} status 逾時，請確認韌體和 USB 連接埠。")


def parse_report(lines, calibration=False):
    name = 'CAL' if calibration else 'LOG'
    prefix = '# cal=' if calibration else '# run='
    end = f'# END {name}'
    report = []
    rows = None
    columns = None
    count = 0
    last_cal_sample = None
    for line in lines:
        if line in (f'{name} BUSY', f'NO SAVED {name} AT THAT RANK') or line.startswith('ERROR '):
            raise ValueError(line)
        if not report:
            if not line.startswith(prefix):
                continue  # Buffered boot and unsolicited status messages.
            match = re.search(r'\brows=(\d+)\b', line)
            if not match or int(match[1]) > (5 if calibration else 108):
                raise ValueError("紀錄開頭的列數無效。")
            rows = int(match[1])
        elif line.startswith('# END '):
            if line != f'{end} rows={rows}' or columns is None or count != rows:
                raise ValueError("結束標記或資料列數不符，紀錄不完整。")
            return '\n'.join(report + [line]) + '\n'
        elif line.startswith('#'):
            if line.startswith(('# run=', '# cal=')):
                raise ValueError("上一份紀錄尚未結束。")
        elif columns is None:
            columns = next(csv.reader([line]))
            if calibration:
                if columns != ['sample', 'position_step', 'elapsed_ms', 'gap_steps', 'interval_ms']:
                    raise ValueError("無法辨識校正紀錄的 CSV 欄位。")
            elif columns[:2] != ['card', 'player_0_remainder'] or 'qualified_edges' not in columns:
                raise ValueError("無法辨識紀錄的 CSV 欄位。")
        else:
            cells = next(csv.reader([line]))
            if (len(cells) != len(columns) or cells[0] != str(count + 1) or count >= rows
                    or any(not re.fullmatch(r'-?\d+', field) for field in cells)):
                raise ValueError("紀錄的序號或欄位不完整。")
            if calibration:
                position, elapsed, gap, interval = map(int, cells[1:])
                expected = (-1, -1) if last_cal_sample is None else (position-last_cal_sample[0], elapsed-last_cal_sample[1])
                if elapsed < 0 or (gap, interval) != expected:
                    raise ValueError("校正紀錄的兩次感測位置或時間與間隔欄位不符。")
                last_cal_sample = (position, elapsed)
            count += 1
        report.append(line)
    raise ValueError(f"未收到完整的 {end}，請確認連線後再讀一次。")


def main(argv=None):
    parser = argparse.ArgumentParser(description="經 USB 讀取發牌機測試紀錄")
    parser.add_argument('--port', help='指定 USB 序列埠，例如 COM5')
    parser.add_argument('--calibration', action='store_true', help='讀取獨立保存的圈數校正紀錄')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--rank', type=int, choices=range(1, 5), default=1, help='1 為最新，4 為最舊')
    group.add_argument('--status', action='store_true', help='只查詢儲存狀態')
    parser.add_argument('--output', type=Path, help='將完整結果存成檔案，省略時輸出到終端機')
    parser.add_argument('--timeout', type=int, default=30, help='等待匯出的最長秒數，預設 30')
    options = parser.parse_args(argv)
    if not 1 <= options.timeout <= 300:
        parser.error('--timeout 應介於 1 至 300 秒')
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        parser.exit(2, '缺少 pyserial。請先執行 python -m pip install pyserial\n')
    try:
        name = options.port or select_port(list_ports.comports())
        # Set both lines inactive before open. Never send a reset sequence or
        # firmware commands that start, stop, flash or erase the device.
        port = serial.Serial(port=None, baudrate=115200, timeout=0.15, write_timeout=2)
        port.dtr = False
        port.rts = False
        port.port = name
        with port:
            status = read_status(port, min(options.timeout, 10), options.calibration)
            if options.status:
                result = status + '\n'
            else:
                if ' recording=1 ' in status or status.endswith(' export=1'):
                    raise ValueError("發牌或匯出仍在進行，請在結束後讀取。")
                command = 'cal' if options.calibration else 'log'
                port.write(f'{command} export {options.rank}\n'.encode('ascii'))
                result = parse_report(read_lines(port, time.monotonic() + options.timeout, 10), options.calibration)
        if options.output:
            options.output.write_text(result, encoding='utf-8')
        else:
            sys.stdout.write(result)
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(1, f'讀取失敗：{exc}\n')


if __name__ == '__main__':
    main()
