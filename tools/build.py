#!/usr/bin/env python3
"""Build a multi-package Cydia source with the standard Debian indexer."""
import argparse
import bz2
from collections import defaultdict
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def parse_index(text):
    records = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        fields, current = {}, None
        for line in block.splitlines():
            if line.startswith((" ", "\t")) and current:
                fields[current] += "\n" + line
                continue
            key, separator, value = line.partition(":")
            if not separator or not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", key):
                raise ValueError("Invalid Packages field")
            if key.lower() in {k.lower() for k in fields}:
                raise ValueError(f"Duplicate Packages field: {key}")
            fields[key] = value.lstrip()
            current = key
        records.append(fields)
    if not records:
        raise ValueError("No package records; refusing to publish an empty source")
    return records


def validate_records(root, records, package_dir="packages"):
    identities, indexed = set(), set()
    for record in records:
        for key in ("Package", "Version", "Architecture", "Description", "Maintainer", "Filename", "Size", "SHA256"):
            if not record.get(key):
                raise ValueError(f"Missing package metadata: {key}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", record["Package"]):
            raise ValueError("Invalid package identifier")
        if not re.fullmatch(r"[0-9][A-Za-z0-9.+~:-]*", record["Version"]):
            raise ValueError("Invalid package version")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", record["Architecture"]):
            raise ValueError("Invalid package architecture")
        identity = tuple(record[key] for key in ("Package", "Version", "Architecture"))
        if identity in identities:
            raise ValueError(f"Duplicate package/version/architecture: {identity}")
        identities.add(identity)
        filename = record["Filename"]
        path = root / filename
        if (not re.fullmatch(re.escape(package_dir) + r"/[A-Za-z0-9._+~/:-]+\.deb", filename)
                or ".." in Path(filename).parts or path.is_symlink()
                or not path.resolve().is_relative_to((root / package_dir).resolve())):
            raise ValueError(f"Unsafe package path: {filename}")
        data = path.read_bytes()
        if len(data) != int(record["Size"]):
            raise ValueError(f"Package size mismatch: {filename}")
        for field, algorithm in (("MD5sum", "md5"), ("SHA1", "sha1"), ("SHA256", "sha256")):
            if field in record and record[field] != hashlib.new(algorithm, data).hexdigest():
                raise ValueError(f"{field} mismatch: {filename}")
        indexed.add(path.resolve())
    actual = {path.resolve() for path in (root / package_dir).rglob("*.deb")}
    if actual != indexed:
        raise ValueError("Some .deb files are missing from the index, or unexpected files were indexed")


def web_link(value):
    parsed = urlparse(value)
    return value if parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username else None


def render(config, records):
    escape = html.escape
    groups = defaultdict(list)
    for record in records:
        groups[record["Package"]].append(record)
    cards = []
    for package_id, releases in sorted(groups.items()):
        first = releases[0]
        description = first["Description"].splitlines()[0]
        detail = web_link(first.get("Depiction", first.get("Homepage", "")))
        link = f'<a href="{escape(detail, quote=True)}">Details and requirements</a>' if detail else "Read the package requirements in Cydia."
        versions = []
        for release in releases:
            versions.append(f'<li><a href="{quote(release["Filename"], safe="/-._~")}">Download {escape(release["Version"])}</a> <span class="meta">{escape(release["Architecture"])} · {int(release["Size"]):,} bytes</span></li>')
        cards.append(f'<article><h3>{escape(first.get("Name", package_id))}</h3><p>{escape(description)}</p><p class="detail">{link}</p><ul class="downloads">{"".join(versions)}</ul></article>')
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(config['name'])}</title><meta name="description" content="{escape(config['description'], quote=True)}">
<link rel="stylesheet" href="style.css"></head><body><main>
<header><p class="eyebrow">Tweaks by {escape(config['author'])}</p><h1>{escape(config['name'])}</h1><p class="lead">{escape(config['description'])}</p></header>
<section class="source"><h2>Add to Cydia</h2><code>{escape(config['base_url'])}</code><p>Sources → Edit → Add. Enter this address, then refresh.</p></section>
<section class="catalog"><h2>Available tweaks</h2><p class="meta">{len(groups)} tweak(s) · {len(records)} release(s)</p>{''.join(cards)}</section>
<section class="info"><h2>One source for future releases</h2><p>Keep this source in Cydia. New tweaks appear when Sources refreshes, and newer versions of your installed tweaks appear as available updates. You choose when to install them.</p><p>Check each tweak’s device and iOS requirements before installing.</p></section>
<footer>By {escape(config['author'])} · <a href="{escape(config['github_url'], quote=True)}">GitHub repository</a> · <a href="{escape(config['github_url'], quote=True)}/issues">Source support</a> · <a href="LICENSE.txt">MIT repository tooling</a></footer>
</main></body></html>'''


CSS = """*{-webkit-box-sizing:border-box;box-sizing:border-box}html{background:#eef1f6;color:#273348;font-family:Helvetica,Arial,sans-serif;-webkit-text-size-adjust:100%}body{margin:0}main,header,section,article,footer{display:block}main{max-width:900px;margin:auto;padding:44px 26px}header{padding:0 0 22px}.eyebrow{text-transform:uppercase;font-size:12px;font-weight:bold;letter-spacing:1.6px;color:#58708f}h1{font-size:40px;line-height:1.15;letter-spacing:-1px;margin:15px 0;word-wrap:break-word}.lead{font-size:20px;line-height:1.6;max-width:620px}h2{font-size:22px;margin:0 0 12px}h3{font-size:23px;margin:0 0 10px;word-wrap:break-word}p,li{font-size:15px;line-height:1.65}a{color:#245aa7}a:hover{color:#16376a}.source{padding:25px 28px;border-radius:12px;background:#18335b;color:#fff;margin:15px 0 34px}.source code{font-family:Menlo,Consolas,monospace;font-size:20px;word-wrap:break-word}.source p{color:#d7e2f2;margin-bottom:0}.meta{color:#68768c;font-size:13px}article,.info{background:#fff;border:1px solid #dce2eb;border-radius:12px;padding:27px;margin:18px 0}.detail{margin-bottom:20px}.downloads{list-style:none;padding:0;margin:0;border-top:1px solid #e2e7ee}.downloads li{padding:14px 0 0}.downloads .meta{display:block;margin-top:3px}.info{background:#f7f9fc;margin-top:30px}.info p:last-child{margin-bottom:0}footer{font-size:12px;line-height:1.8;color:#617087;margin-top:26px}@media(max-width:520px){main{padding:28px 17px}h1{font-size:31px}h3{font-size:21px}.lead{font-size:18px}.source,article,.info{padding:22px 20px}.source code{font-size:17px}}
"""


def build(root=ROOT, index_text=None):
    root = Path(root).resolve()
    config = json.loads((root / "repository.json").read_text())
    for key, value in config.items():
        if not isinstance(value, str) or not value or any(c in value for c in "\n\r\0"):
            raise ValueError(f"Invalid repository setting: {key}")
    if not config["base_url"].startswith("https://") or not config["base_url"].endswith("/") or not web_link(config["github_url"]):
        raise ValueError("Invalid public URLs")
    if index_text is None:
        result = subprocess.run(["dpkg-scanpackages", "--multiversion", "packages", "/dev/null"], cwd=root, capture_output=True, text=True, check=True)
        index_text = result.stdout
    records = parse_index(index_text)
    validate_records(root, records)
    output = root / "site"
    # site/ is generated, ignored by Git, and never contains input files.
    if output.exists():
        if output.is_symlink():
            raise ValueError("Refusing to replace a symlinked site directory")
        shutil.rmtree(output)
    output.mkdir()
    for record in records:
        original = root / record["Filename"]
        # Avoid packages/ colliding with the Packages file on macOS volumes.
        record["Filename"] = "debs/" + record["Filename"].removeprefix("packages/")
        destination = output / record["Filename"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
    packages = ("\n".join("".join(f"{key}: {value}\n" for key, value in record.items()) for record in records) + "\n").encode()
    for name, data in (("Packages", packages), ("Packages.gz", gzip.compress(packages, mtime=0)), ("Packages.bz2", bz2.compress(packages))):
        (output / name).write_bytes(data)
    fields = {"Origin": config["name"], "Label": config["label"], "Suite": "stable", "Version": "1.0", "Codename": "crosbyxii",
              "Architectures": " ".join(sorted({r["Architecture"] for r in records})), "Components": "main", "Description": config["description"]}
    release = "".join(f"{key}: {value}\n" for key, value in fields.items())
    for field, algorithm in (("MD5Sum", "md5"), ("SHA1", "sha1"), ("SHA256", "sha256")):
        release += field + ":\n"
        for name in ("Packages", "Packages.gz", "Packages.bz2"):
            data = (output / name).read_bytes()
            release += f" {hashlib.new(algorithm, data).hexdigest()} {len(data)} {name}\n"
    (output / "Release").write_text(release)
    (output / "index.html").write_text(render(config, records))
    (output / "style.css").write_text(CSS)
    shutil.copyfile(root / "LICENSE", output / "LICENSE.txt")
    (output / ".nojekyll").touch()
    (output / "catalog.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"Built {len(records)} releases for {len({r['Package'] for r in records})} packages in site/.")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, help="Use an existing index for a local preview instead of invoking dpkg-scanpackages")
    args = parser.parse_args()
    build(index_text=args.index.read_text() if args.index else None)
