"""Endpoint implementation is registered through the consolidated REST blueprint.
See docs/api-documentation.md for routes and payload contracts.
"""
from legacy_app.api import api
blueprint = api
