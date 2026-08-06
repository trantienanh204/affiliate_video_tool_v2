"""Gradio dark theme tuned for affiliate creator workflow."""

from __future__ import annotations

import gradio as gr


def build_theme() -> gr.Theme:
    """Return a dark, high-contrast theme."""
    return gr.themes.Soft(
        primary_hue="violet",
        secondary_hue="slate",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Inter"),
    ).set(
        body_background_fill="#0f0f12",
        body_background_fill_dark="#0f0f12",
        block_background_fill="#1a1a22",
        block_background_fill_dark="#1a1a22",
        block_border_width="1px",
        block_border_color="#2a2a35",
        block_label_text_color="#e0e0e8",
        block_title_text_color="#ffffff",
        button_primary_background_fill="#7c3aed",
        button_primary_background_fill_hover="#6d28d9",
        button_primary_text_color="#ffffff",
        input_background_fill="#121218",
        input_border_color="#333340",
        border_color_primary="#333340",
    )
