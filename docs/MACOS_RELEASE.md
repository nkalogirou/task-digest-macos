# Building signed macOS releases

Task Digest can be distributed as a self-contained `.app`, `.dmg`, and `.zip`.
People who install the release do **not** need Python or a source checkout. On first
launch, the app stores its data under `~/Library/Application Support/Task Digest`,
asks for an Asana personal access token, stores that token in macOS Keychain, and
lets the user choose an Asana workspace. GitHub support remains optional and uses
GitHub CLI when it is installed and authenticated.

## Local unsigned build

On macOS with Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-macos.txt
scripts/build_release.sh
```

This produces an ad-hoc signed test build in `release/`. Gatekeeper may warn when
another person opens an ad-hoc signed build.

## Developer ID signing and notarization

Public downloads should be signed with a **Developer ID Application** certificate,
use the hardened runtime, and be notarized by Apple. Set these environment values:

```text
APPLE_SIGNING_IDENTITY=Developer ID Application: Your Name (TEAMID)
APPLE_ID=your-apple-id@example.com
APPLE_APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx
APPLE_TEAM_ID=TEAMID
NOTARIZE=1
```

Then run:

```bash
scripts/build_release.sh
```

The script signs bundled Mach-O files, signs the app with the hardened runtime,
verifies the signature, submits it with `notarytool`, staples the ticket, creates a
DMG and ZIP, and writes SHA-256 checksums.

## GitHub Actions secrets

The `Build macOS release` workflow supports these repository secrets:

| Secret | Meaning |
|---|---|
| `APPLE_CERTIFICATE_P12_BASE64` | Base64-encoded exported Developer ID Application `.p12` certificate |
| `APPLE_CERTIFICATE_PASSWORD` | Password used when exporting the `.p12` |
| `APPLE_SIGNING_IDENTITY` | Full `Developer ID Application: ...` identity name |
| `APPLE_ID` | Apple ID used for notarization |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific Apple ID password |
| `APPLE_TEAM_ID` | Apple Developer Team ID |

Create a version tag to build and attach release assets:

```bash
git tag -a v1.0.13 -m "Task Digest v1.0.13"
git push origin v1.0.13
```

If signing secrets are absent, the workflow still produces an ad-hoc signed test
artifact, but it should not be promoted as a trusted public download.
