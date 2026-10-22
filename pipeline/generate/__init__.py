"""Route generation stage."""


class GenerationError(Exception):
    """Raised when a route cannot be generated (e.g. a missing prerequisite in a full route)."""
