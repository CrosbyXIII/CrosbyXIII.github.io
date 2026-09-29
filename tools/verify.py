#!/usr/bin/env python3
"""Check every generated package and index, plus local website links."""
import bz2
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlparse
from build import ROOT, parse_index, validate_records


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []
    def handle_starttag(self, tag, attrs):
        self.values.extend(value for key, value in attrs if key in ("href", "src"))


def verify(root=ROOT):
    root = Path(root)
    site = root / "site"
    data = (site / "Packages").read_bytes()
    assert gzip.decompress((site / "Packages.gz").read_bytes()) == data
    assert bz2.decompress((site / "Packages.bz2").read_bytes()) == data
    records = parse_index(data.decode())
    validate_records(site, records, package_dir="debs")
    assert json.loads((site / "catalog.json").read_text()) == records
    for record in records:
        original = root / "packages" / record["Filename"].removeprefix("debs/")
        assert (site / record["Filename"]).read_bytes() == original.read_bytes()
    algorithm, checks = None, 0
    for line in (site / "Release").read_text().splitlines():
        if line in ("MD5Sum:", "SHA1:", "SHA256:"):
            algorithm = {"MD5Sum:": "md5", "SHA1:": "sha1", "SHA256:": "sha256"}[line]
        elif line.startswith(" "):
            checksum, size, name = line.split()
            body = (site / name).read_bytes()
            assert int(size) == len(body) and checksum == hashlib.new(algorithm, body).hexdigest()
            checks += 1
    assert checks == 9
    links = Links()
    links.feed((site / "index.html").read_text())
    for value in links.values:
        url = urlparse(value)
        if url.scheme:
            assert url.scheme in ("http", "https")
            continue
        path = (site / unquote(url.path)).resolve()
        assert path.is_relative_to(site.resolve()) and path.is_file(), value
    print(f"PASS: {len(records)} package records, payload hashes, compressed indexes, Release checksums, and website links")


if __name__ == "__main__":
    verify()
