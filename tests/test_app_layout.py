"""Tests for App Layout and Gradio Blocks construction."""

import pytest
from app.main import create_app


def test_create_app_blocks():
    """Verify that Gradio application blocks can be created cleanly."""
    demo = create_app()
    assert demo is not None
    assert demo.title == "AI Video Studio & Fast Story"
