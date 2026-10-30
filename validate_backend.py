"""Run upstream tests with local V15; skip Linux symlink fixtures on Windows."""
import os
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
os.environ['FM1_V15_FWSC'] = str(root / 'FM-1_015.fwsc')
os.environ['FM1_JLUB_DIR'] = str(root / 'upstream/jl-uboot-tool')
sys.path.insert(0, str(root / 'upstream'))
from tests import test_unbrick, test_transporter

if sys.platform == 'win32':
    for name in ('test_linux_sysfs', 'test_two_devices_refused'):
        setattr(test_unbrick.FinderTests, name,
                unittest.skip('Linux sysfs symlink fixture needs Windows symlink privilege')(
                    getattr(test_unbrick.FinderTests, name)))
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                           for m in (test_unbrick, test_transporter))
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
