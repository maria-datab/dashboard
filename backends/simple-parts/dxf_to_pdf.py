"""Render branch DXF files to a multi-page A4 landscape PDF."""

from __future__ import annotations

import math
from io import BytesIO

import matplotlib

matplotlib.use("Agg")

import ezdxf
import matplotlib.pyplot as plt
from ezdxf import bbox as ezdxf_bbox
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import LayoutProperties
from matplotlib.backends.backend_pdf import PdfPages

from dxf_serializer import apply_nesting_layer_colors, exclude_layers as exclude_layers_from_doc
from layer_scheme import LAYER_PLATE

A4_LANDSCAPE_INCHES = (11.69, 8.27)
A4_LANDSCAPE_MM = (297.0, 210.0)
PAGE_MARGIN_MM = 15.0
SCALE_STEP = 10
LABEL_MARGIN = 0.02


def load_branch_doc(path: str, exclude_layers: set[str] | None = None):
    """Load a branch DXF, optionally strip layers, and apply nesting colors."""
    doc = ezdxf.readfile(path)
    if exclude_layers:
        exclude_layers_from_doc(doc, exclude_layers)
    apply_nesting_layer_colors(doc)
    return doc


def _content_bbox(doc) -> tuple[float, float, float, float] | None:
    """Return xmin, ymin, xmax, ymax for the sheet/content area."""
    msp = doc.modelspace()
    plate_entities = [entity for entity in msp if entity.dxf.layer == LAYER_PLATE]
    entities = plate_entities if plate_entities else list(msp)
    if not entities:
        return None

    extents = ezdxf_bbox.extents(entities)
    if not extents.has_data:
        return None

    return (
        float(extents.extmin.x),
        float(extents.extmin.y),
        float(extents.extmax.x),
        float(extents.extmax.y),
    )


def _choose_scale_denominator(content_w: float, content_h: float) -> int:
    """Pick the smallest 1:N scale (N multiple of 10) so content fits on A4 with margins."""
    page_w, page_h = A4_LANDSCAPE_MM
    usable_w = page_w - 2 * PAGE_MARGIN_MM
    usable_h = page_h - 2 * PAGE_MARGIN_MM

    if content_w <= 0 or content_h <= 0:
        raise ValueError("content bbox has zero area")

    n_min = max(
        math.ceil(content_w / usable_w),
        math.ceil(content_h / usable_h),
    )
    return max(SCALE_STEP, math.ceil(n_min / SCALE_STEP) * SCALE_STEP)


def _scale_viewport_limits(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    scale_denominator: int,
) -> tuple[float, float, float, float]:
    """Return axis limits that center content on A4 at scale 1:scale_denominator."""
    page_w, page_h = A4_LANDSCAPE_MM
    view_w = page_w * scale_denominator
    view_h = page_h * scale_denominator
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2

    return (
        cx - view_w / 2,
        cx + view_w / 2,
        cy - view_h / 2,
        cy + view_h / 2,
    )


def _add_scale_label(fig: plt.Figure, scale_denominator: int | None) -> None:
    if scale_denominator is None:
        label = "Scale —"
    else:
        label = f"Scale 1:{scale_denominator}"

    fig.text(
        LABEL_MARGIN,
        LABEL_MARGIN,
        label,
        ha="left",
        va="bottom",
        fontsize=9,
        color="#333333",
    )


def _render_page(doc, dpi: int) -> plt.Figure:
    fig = plt.figure(figsize=A4_LANDSCAPE_INCHES, dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.margins(0)
    ax.set_aspect("equal")
    ax.set_axis_off()

    ctx = RenderContext(doc)
    msp = doc.modelspace()
    props = LayoutProperties.from_layout(msp)
    props.set_colors("#ffffff")
    out = MatplotlibBackend(ax)

    bounds = _content_bbox(doc)
    scale_denominator = None
    if bounds is None:
        Frontend(ctx, out).draw_layout(msp, finalize=True, layout_properties=props)
    else:
        xmin, ymin, xmax, ymax = bounds
        content_w = xmax - xmin
        content_h = ymax - ymin
        scale_denominator = _choose_scale_denominator(content_w, content_h)
        lim_xmin, lim_xmax, lim_ymin, lim_ymax = _scale_viewport_limits(
            xmin,
            ymin,
            xmax,
            ymax,
            scale_denominator,
        )
        ax.set_xlim(lim_xmin, lim_xmax)
        ax.set_ylim(lim_ymin, lim_ymax)
        Frontend(ctx, out).draw_layout(msp, finalize=False, layout_properties=props)

    _add_scale_label(fig, scale_denominator)
    return fig


def render_branch_dxfs_to_pdf(
    branch_paths: list[str],
    *,
    exclude_layers: set[str] | None = None,
    dpi: int = 300,
) -> bytes:
    """Render each branch DXF to an A4 landscape page and return merged PDF bytes."""
    if not branch_paths:
        raise ValueError("branch_paths must not be empty")

    excluded = exclude_layers or set()
    buffer = BytesIO()

    with PdfPages(buffer) as pdf:
        for path in branch_paths:
            doc = load_branch_doc(path, excluded)
            fig = _render_page(doc, dpi)
            try:
                pdf.savefig(fig)
            finally:
                plt.close(fig)

    return buffer.getvalue()
