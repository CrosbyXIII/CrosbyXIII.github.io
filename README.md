# CrosbyXII's Cydia Repository

Tweaks by **CrosbyXII**, hosted on the **CrosbyXIII** GitHub account.

**Permanent Cydia source: https://crosbyxiii.github.io/**

Add that address in **Cydia → Sources → Edit → Add**. Refresh Sources to see new tweaks and updates. Cydia offers updates for an installed package when its `Package` identifier stays the same and a higher Debian `Version` is published. Updates are not silently installed.

The first package is [iTunesAppStorePageFixer](https://github.com/CrosbyXIII/iTunesAppStorePageFixer). Its original source URL remains available; this general source is the recommended address for future tweaks. Adding it does not require reinstalling a tweak. After it loads successfully, you can remove the older tweak-specific source to avoid duplicate listings.

## Publish another tweak or update

1. Build and test a `.deb` installer. Set its public `Name`, stable `Package` ID, `Version`, `Architecture`, `Description`, dependencies, and `Author` in its control metadata. Use **CrosbyXII** as the public author. For updates, keep the same ID and increase the version, for example `0.3.0~beta1` → `0.3.0~beta2` → `0.3.0` → `0.3.1`.
2. Upload the new file to this repository's **packages/** folder using GitHub's **Add file → Upload files**, or copy it there locally and push a commit to `main`. Use a unique filename such as `package.id_1.0.0_iphoneos-arm.deb`; keep previously published files for existing downloads. Do not replace an existing release with different bytes under the same version.
3. The **Publish Cydia repository** Action validates the package catalog, regenerates the website, compressed APT indexes, and checksums, then deploys them to GitHub Pages. Wait for its green check.
4. Refresh Cydia on a device and check the new listing or update.

You do **not** need to edit `Packages` or create another source URL. A new GitHub source-code repository alone does not publish a tweak: put its tested installer in **packages/** here. Each tweak can retain its own source-code repository, documentation, issue tracker, and Cydia depiction page.

For iOS 5 packages, use the legacy `iphoneos-arm` architecture and gzip-compressed control/data tar members; modern package formats and dependencies may not work on old devices. The general repository does not make every package compatible with every device. Read each package's requirements.

## How the repository is built

- `repository.json`: public repository name, description, author, and URLs.
- `packages/*.deb`: release installers. GitHub publishes only the packages and generated site, not arbitrary local files.
- `tools/build.py`: runs the standard Debian `dpkg-scanpackages --multiversion` tool, preserves package metadata, checks payload sizes/hashes and duplicate identities, and writes `site/`.
- `.github/workflows/publish.yml`: automatically builds and publishes changes pushed to `main`; pull requests are checked but never deployed.

All published versions are indexed; Cydia/APT compares their Debian versions and selects eligible updates. The package metadata's dependencies and compatibility restrictions remain in effect. Checksums detect inconsistent downloads; the repository is served over HTTPS and is not GPG-signed.

To build locally on Linux with Python 3.9+ and `dpkg-dev`:

```sh
python3 -m unittest discover -s tests -v
python3 tools/build.py
python3 tools/verify.py
python3 -m http.server 8080 --bind 127.0.0.1 --directory site
```

On macOS without `dpkg-scanpackages`, use the GitHub Action to build, or install the Debian packaging tools separately. `--index PATH` is available for local previews using an already-generated `Packages` file; normal publishing always scans the real `.deb` files.

## Availability and support

The catalog and downloads can be verified on the web independently of installation. Each release still needs testing in Cydia on its supported devices. The initial PageFixer library has been tested on an iPad 1 running iOS 5.1.1 with separate store repairs; see its [test notes](https://github.com/CrosbyXIII/iTunesAppStorePageFixer/blob/main/TESTING.md).

Use this repository's Issues for source/catalog problems, and each tweak's own issue tracker for tweak-specific problems. Do not post account credentials or full device logs.

Repository tooling and website: MIT, copyright 2026 CrosbyXII. Individual packages retain their own licenses. The included PageFixer is MIT-licensed.
