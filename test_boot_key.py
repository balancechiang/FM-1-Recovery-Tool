import unittest
from unittest.mock import patch
import offline_recover as app


class Output:
    def __init__(self, names):
        self.names, self.sent, self.opened = names, [], []
        self.closed = self.deleted = False
    def get_ports(self): return self.names
    def open_port(self, i): self.opened.append(i)
    def send_message(self, msg): self.sent.append(msg)
    def close_port(self): self.closed = True
    def delete(self): self.deleted = True


class BootKeyTests(unittest.TestCase):
    def test_language_selection_reprompts(self):
        with patch('builtins.input', side_effect=['invalid', '2']), patch('builtins.print'):
            self.assertEqual(app.choose_language(), 'zh')

    def test_single_language_prompts_and_console(self):
        import logging
        for lang, expected in [('en', 'Cancelled.'), ('zh', '已取消。')]:
            with patch.object(app, 'LANGUAGE', lang):
                self.assertEqual(app.localize('已取消。 / Cancelled.'), expected)
                record = logging.LogRecord('test', logging.INFO, '', 0, 'Step 1/6: package', (), None)
                result = app.LanguageProgress().format(record)
                self.assertEqual(result, 'Step 1/6: package' if lang == 'en' else '步骤 1/6：校验固件包')
                self.assertEqual(record.getMessage(), 'Step 1/6: package')

    def test_confirmation_case_insensitive(self):
        for value in ('V15', 'v15', ' V15 ', ' v15\n'):
            self.assertTrue(app.confirm_v15(value))
        for value in ('RESTORE', '', 'V16', 'v 15'):
            self.assertFalse(app.confirm_v15(value))

    def invoke(self, names):
        out = Output(names)
        class RT:
            def MidiOut(self): return out
            def MidiIn(self): raise AssertionError('must not open an input')
        with patch.object(app.time, 'sleep'):
            app.send_boot_key(RT())
        return out

    def test_no_identity_or_input_required(self):
        out = self.invoke(['Other keyboard', 'FM-1 1'])
        self.assertEqual(out.opened, [1])
        self.assertEqual(out.sent, [[240, 34, 36, 53, 125, 247]])
        self.assertTrue(out.closed and out.deleted)

    def test_custom_firmware_name(self):
        self.assertEqual(self.invoke(['Felucca']).opened, [0])

    def test_no_matching_port(self):
        with self.assertRaises(RuntimeError): self.invoke(['Other keyboard'])

    def test_multiple_ports_refused(self):
        with self.assertRaises(RuntimeError): self.invoke(['FM-1', 'FM-1 2'])


if __name__ == '__main__': unittest.main()
