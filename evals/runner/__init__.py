"""Backend-neutral agent evaluation engine.

Magister-specific transport and credentials belong in ``adapters``.  The core
modules intentionally depend only on the Python standard library so they can
be extracted into a standalone package later.
"""

from .schema import Candidate, Experiment, ManifestError, Scenario, Trial

__all__ = [
    "Candidate",
    "Experiment",
    "ManifestError",
    "Scenario",
    "Trial",
]
