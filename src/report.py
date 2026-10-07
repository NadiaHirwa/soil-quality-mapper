"""Multi-page PDF parcel evaluation report (Matplotlib PdfPages, no extra library).

Each page is a Matplotlib figure: text pages have no axes, map pages come
from src.plots, and the parcel table is drawn with ax.table. Every figure
is closed right after it is added to the PDF.
"""

import io
import textwrap
from datetime import date

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from src import config
from src.fertility import FieldAssessment, field_summary
from src.plots import plot_fertility_map, plot_limiting_factor_map, plot_property_map


def _text_page(title: str, sections: list[tuple[str, list[str]]], footer: str = "") -> Figure:
    """An A4 landscape page with a title and headed sections of wrapped text lines."""
    fig = plt.figure(figsize=config.PDF_PAGE_SIZE)
    y = 0.92
    fig.text(0.06, y, title, fontsize=18, fontweight="bold", color=config.INK_COLOR)
    y -= 0.06
    for heading, lines in sections:
        fig.text(0.06, y, heading, fontsize=12, fontweight="bold", color=config.INK_COLOR)
        y -= 0.035
        for line in lines:
            for k, part in enumerate(textwrap.wrap(line, width=120)):
                fig.text(0.08 if k == 0 else 0.095, y, ("- " if k == 0 else "") + part,
                         fontsize=10, color=config.INK_COLOR)
                y -= 0.027
        y -= 0.02
    if footer:
        fig.text(0.06, 0.05, footer, fontsize=9, style="italic", color=config.INK_COLOR)
    return fig


def _title_page(assessment: FieldAssessment, data_source: str, created: date) -> Figure:
    """Title page: field, date, data source, summary numbers and disclaimer."""
    summary = field_summary(assessment)
    area = summary["pct_area"]
    parcels = summary["parcels_by_class"]
    power_text = ", ".join(f"{p} {assessment.powers[p]:g}" for p in config.NUMERIC_COLUMNS)
    sections = [
        ("Field and data", [
            config.FIELD_DESCRIPTION,
            f"Data source: {data_source}.",
            f"Samples used: {summary['samples_used']} (from {summary['rows_in']} raw rows).",
            f"Report created: {created.isoformat()}.",
        ]),
        ("Summary", [
            f"Share of field area: Good {area['Good']:.1f}%, Moderate {area['Moderate']:.1f}%, "
            f"Poor {area['Poor']:.1f}%.",
            f"Parcels ({summary['n_parcels']} x 1 ha): Good {parcels['Good']}, "
            f"Moderate {parcels['Moderate']}, Poor {parcels['Poor']}.",
            f"Main limiting factor across the field: {summary['main_limiting_factor']}.",
            f"IDW power used: {power_text} "
            f"({'set manually' if assessment.manual_power is not None else 'chosen by cross-validation'}).",
            "Flagged outliers " + ("excluded from" if assessment.exclude_outliers else "included in")
            + " the maps.",
        ]),
        ("Contents", [
            "Fertility map; limiting-factor map; maps of pH, nitrogen, phosphorus and salinity; "
            "parcel table; methods, assumptions and limitations.",
        ]),
    ]
    return _text_page(config.REPORT_TITLE, sections, footer=config.REPORT_DISCLAIMER)


def _parcel_table_pages(parcels: pd.DataFrame) -> list[Figure]:
    """The key parcel columns as a table, split over pages of PDF_TABLE_ROWS_PER_PAGE rows."""
    table = parcels[list(config.PDF_TABLE_COLUMNS)].rename(columns=config.PDF_TABLE_COLUMNS)
    rows = config.PDF_TABLE_ROWS_PER_PAGE
    chunks = [table.iloc[start:start + rows] for start in range(0, len(table), rows)]
    pages = []
    for number, chunk in enumerate(chunks, start=1):
        fig, ax = plt.subplots(figsize=config.PDF_PAGE_SIZE)
        ax.axis("off")
        ax.set_title(f"Parcel evaluation (page {number} of {len(chunks)})",
                     fontsize=16, fontweight="bold", loc="left")
        # Same number of decimals in every row: 1 for percentages, 2 for means.
        text = chunk.copy().astype(object)
        for column in chunk.columns:
            if pd.api.types.is_float_dtype(chunk[column]):
                decimals = 1 if column.endswith("%") else 2
                text[column] = chunk[column].map(lambda v, d=decimals: f"{v:.{d}f}")
        drawn = ax.table(cellText=text.astype(str).to_numpy(), colLabels=list(chunk.columns),
                         loc="upper center", cellLoc="center")
        drawn.auto_set_font_size(False)
        drawn.set_fontsize(10)
        drawn.auto_set_column_width(list(range(len(chunk.columns))))  # fit the longest text
        drawn.scale(1, 1.7)
        for (row, _), cell in drawn.get_celld().items():
            if row == 0:
                cell.set_text_props(fontweight="bold")
                cell.set_facecolor("#eeeeee")
        footer = ("Means are of the interpolated 5 m grid inside each parcel. The full report "
                  "(min/max, bounds, notes) is in parcel_report.csv. " + config.REPORT_DISCLAIMER)
        fig.text(0.06, 0.05, textwrap.fill(footer, width=150), fontsize=9, style="italic")
        pages.append(fig)
    return pages


def build_pdf_report(
    assessment: FieldAssessment, data_source: str, created: date | None = None
) -> bytes:
    """Multi-page PDF parcel evaluation report, returned as bytes.

    Pages: title page, fertility map, limiting-factor map, one map per soil
    property, the parcel table (as many pages as needed), and a methods page.
    Every figure is closed right after it is added to the PDF.
    """
    a = assessment
    pages = [
        lambda: _title_page(a, data_source, created or date.today()),
        lambda: plot_fertility_map(a.grid_x, a.grid_y, a.class_grid),
        lambda: plot_limiting_factor_map(a.grid_x, a.grid_y, a.limiting_grid),
    ]
    for prop in config.NUMERIC_COLUMNS:
        pages.append(lambda p=prop: plot_property_map(a.grid_x, a.grid_y, a.grids[p], a.clean, p,
                                                      a.powers[p], a.exclude_outliers))
    methods = lambda: _text_page("Methods, assumptions and limitations", [
        ("Method", config.METHOD_STEPS),
        ("Key assumptions", config.KEY_ASSUMPTIONS),
        ("Known limitations", config.LIMITATIONS),
    ], footer=config.REPORT_DISCLAIMER)

    buffer = io.BytesIO()
    metadata = {"Title": config.REPORT_TITLE, "Creator": "Soil Quality Mapper"}
    with PdfPages(buffer, metadata=metadata) as pdf:
        for make_page in pages:
            fig = make_page()
            pdf.savefig(fig)
            plt.close(fig)
        for fig in _parcel_table_pages(a.parcels):
            pdf.savefig(fig)
            plt.close(fig)
        fig = methods()
        pdf.savefig(fig)
        plt.close(fig)
    return buffer.getvalue()


def pdf_page_count(parcel_count: int) -> int:
    """Pages build_pdf_report produces: 8 fixed pages + the parcel table pages."""
    return 8 + -(-parcel_count // config.PDF_TABLE_ROWS_PER_PAGE)  # ceiling division
