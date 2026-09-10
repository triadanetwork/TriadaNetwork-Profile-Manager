"""Triada Network — browser infrastructure and profile management."""

from importlib.metadata import PackageNotFoundError, version

# Read from the installed package rather than repeating the number here. The two
# had already drifted: a wheel built as 0.2.0 reported 0.1.1 through /health and
# in the OpenAPI schema, because releasing means editing pyproject.toml and it is
# the second copy that gets forgotten.
try:
    __version__ = version("triada-network")
except PackageNotFoundError:  # pragma: no cover - only when running from a source tree
    __version__ = "0.0.0+unknown"

__description__ = "Triada Network browser infrastructure and profile management platform"
