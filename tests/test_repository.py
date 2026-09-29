import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build import build, parse_index, validate_records
from verify import verify


def deb(fields):
    def archive(filename=None, data=None):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as tar:
            if filename:
                item = tarfile.TarInfo("./" + filename)
                item.size, item.mode = len(data), 0o644
                tar.addfile(item, io.BytesIO(data))
        return stream.getvalue()
    control = "".join(f"{key}: {value}\n" for key, value in fields.items()).encode()
    result = bytearray(b"!<arch>\n")
    for name, data in (("debian-binary", b"2.0\n"), ("control.tar.gz", archive("control", control)), ("data.tar.gz", archive())):
        result.extend(f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n".encode())
        result.extend(data)
        if len(data) % 2:
            result.extend(b"\n")
    return bytes(result)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "packages").mkdir()
        config = {"name": "Test Repo", "label": "Test", "author": "Test Author", "description": "Test packages", "base_url": "https://example.invalid/", "github_url": "https://github.com/example/repo"}
        (self.root / "repository.json").write_text(json.dumps(config))
        (self.root / "LICENSE").write_text("Synthetic test fixture\n")
        self.records = []
        for package, version in (("test.first", "1.0~beta1"), ("test.first", "1.0"), ("test.second", "2.0")):
            fields = {"Package": package, "Version": version, "Architecture": "iphoneos-arm", "Maintainer": "Test <test@example.invalid>", "Name": "Sample <Tweak>", "Author": "Test Author", "Description": "First line\n second line", "Depiction": "https://example.invalid/details/"}
            data = deb(fields)
            filename = f"packages/{package}_{version}_iphoneos-arm.deb"
            (self.root / filename).write_bytes(data)
            fields.update(Filename=filename, Size=str(len(data)), MD5sum=hashlib.md5(data).hexdigest(), SHA1=hashlib.sha1(data).hexdigest(), SHA256=hashlib.sha256(data).hexdigest())
            self.records.append(fields)

    def tearDown(self):
        self.temp.cleanup()

    def index(self):
        return "\n".join("".join(f"{k}: {v}\n" for k, v in record.items()) for record in self.records) + "\n"

    def test_multiple_tweaks_and_versions_preserve_metadata(self):
        records = build(self.root, self.index())
        self.assertEqual(len(records), 3)
        self.assertEqual(len({r['Package'] for r in records}), 2)
        self.assertEqual(records[0]['Description'], 'First line\n second line')
        self.assertEqual(records[0]['Author'], 'Test Author')
        self.assertEqual(records[0]['Depiction'], 'https://example.invalid/details/')
        self.assertIn('Sample &lt;Tweak&gt;', (self.root / 'site/index.html').read_text())
        verify(self.root)

    def test_changed_payload_is_rejected(self):
        (self.root / self.records[0]['Filename']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'size mismatch'):
            build(self.root, self.index())

    def test_duplicate_identity_is_rejected(self):
        self.records.append(dict(self.records[0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate package/version'):
            build(self.root, self.index())

    def test_incomplete_index_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing from the index'):
            validate_records(self.root, self.records[:1])

    def test_unsafe_path_and_duplicate_field_are_rejected(self):
        self.records[0]['Filename'] = 'packages/../secret.deb'
        with self.assertRaisesRegex(ValueError, 'Unsafe package path'):
            build(self.root, self.index())
        with self.assertRaisesRegex(ValueError, 'Duplicate Packages field'):
            parse_index('Package: test.one\npackage: test.two\n')

    @unittest.skipUnless(shutil.which('dpkg-scanpackages'), 'Native Debian scanner is exercised by the Linux publishing workflow')
    def test_native_scanner_indexes_all_versions(self):
        records = build(self.root)
        self.assertEqual({(r['Package'], r['Version']) for r in records}, {('test.first', '1.0~beta1'), ('test.first', '1.0'), ('test.second', '2.0')})
        self.assertTrue(all(r['Author'] == 'Test Author' for r in records))
        self.assertTrue(all(r['Name'] == 'Sample <Tweak>' for r in records))
        verify(self.root)


if __name__ == '__main__':
    unittest.main()
