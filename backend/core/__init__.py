"""Cross-cutting API primitives shared by every Django app in this project.

Nothing in :mod:`core` may import from a feature app — the dependency only
flows the other way (``accounts`` -> ``core``).
"""
