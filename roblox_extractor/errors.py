from __future__ import annotations


class ExtractorError(Exception):
    pass


class BinaryFormatError(ExtractorError):
    pass


class OutputConflictError(ExtractorError):
    pass
