import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pack", ROOT / "render.py")
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


class RenderTests(unittest.TestCase):
    def test_reject_configuration_injection_and_ambiguous_hosts(self):
        for value in ['https://example.com', '*.example.com', 'example.com:443',
                      'x"\nSecRuleEngine Off', 'a b', '-bad.test', 'a..test', '']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                pack.rules([value])

    def test_host_alternatives_are_escaped_and_anchored(self):
        pattern = pack.host_pattern(['Example.test.', 'second.test'])
        import re
        for host in ['example.test', 'EXAMPLE.TEST:443', 'second.test.']:
            self.assertIsNotNone(re.fullmatch(pattern, host))
        for host in ['other.test', 'exampleXtest', 'example.test.evil.test']:
            self.assertIsNone(re.fullmatch(pattern, host))

    def test_render_checksums_and_api_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'pack'
            pack.render(out, ['protected.test'], 'uploads', 8388608)
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(len(manifest['files']), 5)
            for name, digest in manifest['files'].items():
                data = (out / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                payload = json.loads((out / name.replace('.conf', '.json')).read_text())
                self.assertEqual(payload['raw_conf_text'], data.decode())
                self.assertEqual(data.count(b'id:AUTO'), 1)
                self.assertTrue(data.startswith(b'SecRule'))
            with self.assertRaises(FileExistsError):
                pack.render(out, ['protected.test'], 'uploads', 8388608)

    def test_options_and_no_raw_body_parser_override(self):
        self.assertEqual(len(pack.rules(['x.test'], 'strict')), 6)
        text = '\n'.join(rule for _, rule in pack.rules(['x.test']))
        self.assertIn('@gt 8388608', text)
        self.assertNotIn('requestBodyProcessor', text)
        self.assertNotIn('setvar:', text)
        for kwargs in [{'profile': 'bad'}, {'max_body_bytes': 0}, {'max_body_bytes': 33554433}]:
            with self.assertRaises(ValueError):
                pack.rules(['x.test'], **kwargs)

    def test_checked_in_examples_match_generator(self):
        for profile in ['uploads', 'strict']:
            expected = pack.rules(['protected.example.invalid'], profile)
            actual = sorted((ROOT / 'examples' / profile).glob('*.conf'))
            self.assertEqual([p.read_text() for p in actual], [text for _, text in expected])

    def test_platform_advanced_editor_contract_when_in_checkout(self):
        backend = ROOT.parents[1] / 'backend'
        if not backend.exists():
            self.skipTest('backend source is not included in the standalone publication archive')
        sys.path.insert(0, str(backend))
        from app.services.rule_service import validate_raw_secrule, apply_rule_id, is_raw_only, parse_raw_rule_metadata
        for profile in ['uploads', 'strict']:
            for slug, text in pack.rules(['protected.test'], profile):
                with self.subTest(profile=profile, slug=slug):
                    self.assertEqual(validate_raw_secrule(text), (True, ''))
                    rendered = apply_rule_id(text, 9500001)
                    self.assertEqual(rendered.count('id:9500001'), 1)
                    self.assertTrue(is_raw_only(rendered))
                    self.assertIn(parse_raw_rule_metadata(rendered)['phase'], [1, 2])


if __name__ == '__main__':
    unittest.main()
