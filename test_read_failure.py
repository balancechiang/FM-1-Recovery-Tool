import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parent / 'upstream'))
import fm1_unbrick as fm
from unittest.mock import Mock, patch


class ReadFailureTests(unittest.TestCase):
    def test_startup_transport_retry_rescans_once(self):
        class TransportError(Exception): pass
        jl = SimpleNamespace(SCSIException=TransportError)
        args = SimpleNamespace(device=None, i_know=False)
        dev = object()
        with patch.object(fm, 'find_devices', side_effect=[
                [dict(path='disk3', description='first')],
                [dict(path='disk4', description='second')]]) as scan, \
             patch.object(fm, 'select_device', side_effect=['disk3', 'disk4']), \
             patch.object(fm, 'check_privileges'), \
             patch.object(fm, 'open_real_device', side_effect=[TransportError('lost'), dev]) as op, \
             patch.object(fm.time, 'sleep') as sleep:
            self.assertIs(fm.connect_with_retry(args, jl), dev)
        self.assertEqual(scan.call_count, 2)
        self.assertEqual([c.args[0] for c in op.call_args_list], ['disk3', 'disk4'])
        sleep.assert_called_once_with(10.0)

    def test_startup_retry_is_bounded_and_does_not_bypass_safety(self):
        class TransportError(Exception): pass
        jl = SimpleNamespace(SCSIException=TransportError)
        args = SimpleNamespace(device=None, i_know=False)
        with patch.object(fm, 'find_devices', return_value=[]), \
             patch.object(fm, 'select_device', return_value='disk3'), \
             patch.object(fm, 'check_privileges'), \
             patch.object(fm.time, 'sleep'), \
             patch.object(fm, 'open_real_device', side_effect=TransportError('lost')) as op:
            with self.assertRaisesRegex(fm.UnbrickError, 'failed twice'):
                fm.connect_with_retry(args, jl)
            self.assertEqual(op.call_count, 2)
            op.reset_mock()
            op.side_effect = fm.SafetyError('wrong identity')
            with self.assertRaises(fm.SafetyError): fm.connect_with_retry(args, jl)
            self.assertEqual(op.call_count, 1)

    def test_waits_before_upload_and_before_flash_query(self):
        events = []
        scsi = Mock()
        loader = Mock()
        loader.usb_buffer_size.side_effect = lambda: events.append('buffer') or 512
        jl = SimpleNamespace(JL_LoaderV2=lambda s: loader)
        with patch.object(fm, 'scsi_inquiry', return_value=('WL82', 'UBOOT1.00', '1.00')), \
             patch.object(fm, 'read_retained_ram', return_value=None), \
             patch.object(fm, 'upload_loader', side_effect=lambda *a: events.append('upload')), \
             patch.object(fm.time, 'sleep', side_effect=lambda n: events.append(n)):
            dev = fm.open_real_device('mock', jl, scsi=scsi)
        self.assertEqual(events, [5.0, 'upload', 1.0, 'buffer'])
        dev.close()

    def test_transport_failure_has_address_and_stops(self):
        class Loader:
            calls = 0
            def flash_read(self, addr, size):
                self.calls += 1
                raise OSError('Transfer failed: WinError 31')
        loader = Loader()
        dev = SimpleNamespace(ldr=loader, io_max=512)
        with self.assertRaisesRegex(fm.UnbrickError, '0x4000.*512.*WinError 31'):
            fm.read_flash(dev, 0x4000, 1024, label=None)
        self.assertEqual(loader.calls, 1)


if __name__ == '__main__': unittest.main()
