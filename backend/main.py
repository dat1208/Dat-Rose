#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for Rose (delegates to main package)
"""

import sys
from pathlib import Path

# Ensure the project root is in sys.path for proper package resolution
# This fixes import issues when running from different directories
# Only needed in development mode (PyInstaller handles paths automatically)
if not getattr(sys, 'frozen', False):
    _project_root = Path(__file__).parent.absolute()
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))

# Point TLS at the bundled CA store. PyInstaller freezes certifi's absolute
# path from the build machine into the bundle, so an installed copy otherwise
# fails every HTTPS request with "Could not find a suitable TLS CA certificate
# bundle, invalid path". Setting these before requests is imported keeps the
# whole process on the CA file that actually ships with this build.
try:
    import os
    import certifi

    _ca_bundle = certifi.where()
    if Path(_ca_bundle).is_file():
        os.environ.setdefault("SSL_CERT_FILE", _ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_bundle)
except Exception:
    pass

# Import from the modularized main package
from main import main

if __name__ == "__main__":
        main()
