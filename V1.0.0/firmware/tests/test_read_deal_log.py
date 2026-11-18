import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import read_deal_log as reader


HEADER = ('card,player_0_remainder,target_step,spin_ms,feed_ms,blocked_ms,blocked_step,clear_ms,'
          'clear_step,count_ms,phase_error_steps,release_est_ms,qualified_edges')
ROW = '1,1,0,0,180,240,0,315,0,327,0,147,2'
REPORT = ['# run=14 kind=deal result=complete rows=1', HEADER, ROW, '# END LOG rows=1']
READY = 'LOG storage=ready stored=1/4 recording=0 ram_latest=0 export=0'
CAL_READY = READY.replace('LOG ', 'CAL ')
CAL_FIELDS = 'sample,position_step,elapsed_ms,gap_steps,interval_ms'
CAL = ['# cal=7 result=complete rows=5', CAL_FIELDS, '1,100,400,-1,-1', '2,8252,20400,8152,20000',
       '3,16405,40401,8153,20001', '4,24557,60400,8152,19999', '5,32709,80400,8152,20000', '# END CAL rows=5']


class UsbPort:
    def __init__(self, status, lines):
        self.status = status
        self.lines = lines
        self.pending = bytearray()
        self.writes = []
        self.opened = False

    def __enter__(self):
        if self.dtr or self.rts or self.port != 'COM7':
            raise AssertionError("Incorrect line states or device at open")
        self.opened = True
        return self

    def __exit__(self, *_):
        self.opened = False

    def write(self, command):
        if not self.opened:
            raise AssertionError("Command sent while closed")
        self.writes.append(command)
        if command in (b'log status\n', b'cal status\n'):
            reply = ['BOOT', self.status]
        elif command in (b'log export 2\n', b'cal export 1\n', b'cal export 4\n'):
            reply = self.lines
        else:
            raise AssertionError(f"Unexpected device command {command!r}")
        self.pending.extend(('\r\n'.join(reply) + '\r\n').encode())

    @property
    def in_waiting(self):
        return min(len(self.pending), 7)

    def read(self, n):
        data = self.pending[:n]
        del self.pending[:n]
        return data


class ReadDealLogTests(unittest.TestCase):
    def run_cli(self, port, *args):
        serial = SimpleNamespace(Serial=lambda **kwargs: port)
        ports = [SimpleNamespace(device='COM7', vid=0x303a, pid=0x1001)]
        tools = SimpleNamespace(list_ports=SimpleNamespace(comports=lambda: ports))
        with patch.dict(sys.modules, {'serial': serial, 'serial.tools': tools}):
            reader.main(list(args))

    def test_fragmented_export(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'sample.csv'
            port = UsbPort(READY, REPORT)
            self.run_cli(port, '--rank', '2', '--output', str(file))
            self.assertEqual(file.read_text().splitlines(), REPORT)
            self.assertEqual(port.writes, [b'log status\n', b'log export 2\n'])
            self.assertFalse(port.opened)

    def test_missing_or_wrong_footer_truncated_rows_and_device_errors(self):
        for lines in (REPORT[:-1], REPORT[:2] + REPORT[3:], REPORT[:-1] + ['# END LOG rows=2'],
                      REPORT[:2] + ['2,0'] + REPORT[3:], ['NO SAVED LOG AT THAT RANK'], ['LOG BUSY']):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                reader.parse_report(lines)

    def test_empty_calibration_report(self):
        lines = ['# run=12 kind=calibration rows=0', HEADER, '# END LOG rows=0']
        self.assertEqual(reader.parse_report(lines).splitlines(), lines)

    def test_calibration_export_is_independent(self):
        for rank in (1, 4):
            with self.subTest(rank=rank), tempfile.TemporaryDirectory() as temp:
                out = Path(temp) / 'cal.csv'
                port = UsbPort(CAL_READY, CAL)
                args = ['--calibration', '--output', str(out)]
                if rank == 4:
                    args += ['--rank', '4']
                self.run_cli(port, *args)
                self.assertEqual(port.writes, [b'cal status\n', f'cal export {rank}\n'.encode()])
                self.assertEqual(out.read_text().splitlines(), CAL)
                self.assertFalse(port.opened)
        with tempfile.TemporaryDirectory() as temp:
            port = UsbPort(CAL_READY, [])
            out = Path(temp) / 'status.txt'
            self.run_cli(port, '--calibration', '--status', '--output', str(out))
            self.assertEqual(out.read_text().strip(), CAL_READY)
            self.assertEqual(port.writes, [b'cal status\n'])

    def test_calibration_preserves_partial_and_rejected_evidence(self):
        for rows in ([], ['1,400,40,-1,-1'], ['1,400,40,-1,-1', '2,4800,740,4400,700']):
            n = len(rows)
            lines = [f'# cal=11 result=fault rows={n}', CAL_FIELDS, *rows, f'# END CAL rows={n}']
            self.assertEqual(reader.parse_report(lines, True).splitlines(), lines)

    def test_calibration_rejects_truncated_mixed_or_inconsistent_data(self):
        for lines in (CAL[:-1], CAL[:-1]+['# END LOG rows=5'], CAL[:2]+CAL[3:],
                      [CAL[0], HEADER, *CAL[2:]], CAL[:2]+['1,100,400,0,0']+CAL[3:],
                      CAL[:3]+[CAL[3].replace('8152,20000', '8152,19999')]+CAL[4:],
                      ['# cal=8 rows=6'], ['CAL BUSY'], ['NO SAVED CAL AT THAT RANK']):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                reader.parse_report(lines, True)

    def test_usb_disconnect_before_footer(self):
        port = UsbPort(READY, REPORT[:-1])
        port.pending.extend(('\n'.join(REPORT[:-1]) + '\n').encode())
        ticks = iter(i / 100 for i in range(2000))
        with patch.object(reader.time, 'monotonic', side_effect=ticks), self.assertRaisesRegex(ValueError, 'END LOG'):
            reader.parse_report(reader.read_lines(port, deadline=30, idle_seconds=1))

    def test_busy_and_incomplete_leave_existing_output_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'sample.csv'
            file.write_text('previous report')
            for busy in (False, True):
                port = UsbPort(READY.replace('recording=0', 'recording=1') if busy else READY,
                               REPORT[:-1] + ['# END LOG rows=0'])
                with self.subTest(busy=busy), self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                    self.run_cli(port, '--rank', '2', '--output', str(file))
                self.assertEqual(file.read_text(), 'previous report')
                if busy:
                    self.assertEqual(port.writes, [b'log status\n'])

    def test_status_only_and_ambiguous_devices(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'status.txt'
            port = UsbPort(READY, [])
            self.run_cli(port, '--port', 'COM7', '--status', '--output', str(out))
            self.assertEqual(out.read_text().strip(), READY)
            self.assertEqual(port.writes, [b'log status\n'])
        device = SimpleNamespace(device='COM7', vid=0x303a, pid=0x1001)
        for candidates in ([], [device, device]):
            with self.assertRaises(ValueError):
                reader.select_port(candidates)


if __name__ == '__main__':
    unittest.main()
