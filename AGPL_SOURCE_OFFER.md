# AGPL Source Offer for Ghostscript

This project’s container images include Ghostscript, which is licensed under the GNU Affero General Public License, version 3 (AGPL-3.0).

To satisfy the AGPL’s Corresponding Source requirements, we provide:
- A copy of the AGPL license and Debian copyright metadata under `/licenses/os/ghostscript` in the container image.
- An installed package manifest at `/licenses/os/manifest-dpkg.txt` and Python package manifest at `/licenses/app/pip-freeze.txt` in the container image.

Obtaining Corresponding Source for Ghostscript
- From Debian repositories (preferred):
  1. Identify the installed version inside the image:
     - `grep '^ghostscript ' /licenses/os/manifest-dpkg.txt`
  2. On a Debian/Ubuntu system (or any environment with APT source access), run:
     - `apt-get source ghostscript=<VERSION>`
     - Or browse: https://snapshot.debian.org/package/ghostscript/ and select the exact version.
- From upstream:
  - Ghostscript sources are available from: https://ghostscript.com/releases/ and their source repository.

If you received a binary or are a remote user of a service powered by this software and cannot access the above, you may request a copy of the Corresponding Source for the AGPL-covered components.

Contact for Source Requests
- Please provide a contact email or address for source requests: [maintainer-email@domain]
- Requests should include the image tag/ID and the file `/licenses/os/manifest-dpkg.txt` for precise version mapping.

Notes
- We do not modify Ghostscript; the Corresponding Source is the unmodified upstream source corresponding to the exact binary version present in the image.
- If we ever ship modified Ghostscript, we will provide the complete modified source under the AGPL.

