"""List-compatible search results and safe per-query coverage metadata."""


class SearchResults(list):
    """List-compatible results with safe per-query coverage counts, never raw errors."""

    def __init__(self, items=(), *, statuses=None):
        super().__init__(items)
        self.total = len(statuses) if statuses is not None else 0
        self.responded = sum(type(s) is int and s == 2 for s in statuses or [])
        failed = sum(type(s) is int and s == 1 for s in statuses or [])
        self.availability = (
            "complete"
            if self.total and self.responded == self.total
            else "partial"
            if self.responded
            else "unavailable"
            if self.total and failed == self.total
            else "unknown"
        )
