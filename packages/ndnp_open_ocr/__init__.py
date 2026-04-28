"""NDNP Open OCR pipeline.

Single source of truth for the package version. ``processors.py`` imports
``__version__`` from here, and Terraform regex-extracts the same string for
the Lambda env var, so a release bump is a one-line edit.
"""

__version__ = "1.2.0"
