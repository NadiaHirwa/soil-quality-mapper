"""Shared pytest setup.

Matplotlib's "Agg" backend draws figures in memory only, so tests never try
to open a plot window.
"""

import matplotlib

matplotlib.use("Agg")
