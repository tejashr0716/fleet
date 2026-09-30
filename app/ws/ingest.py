"""Telemetry uses the authenticated REST batch route, not a second ingestion protocol.
Keeping one path makes validation, durability, retry semantics and testing easier to explain.
"""
