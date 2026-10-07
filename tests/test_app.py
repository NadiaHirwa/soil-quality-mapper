"""Tests for Stage 7: the Streamlit app runs (headless, no browser)."""

import matplotlib.pyplot as plt
import pytest
from streamlit.testing.v1 import AppTest

from src import config

TAB_LABELS = ["Data & cleaning", "Maps", "Validation", "Fertility & parcels", "Export"]


@pytest.fixture
def app() -> AppTest:
    # The path is relative to this test file.
    return AppTest.from_file("../app.py", default_timeout=60).run()


def test_runs_with_bundled_data_without_exceptions(app):
    assert not app.exception
    assert not app.error


def test_all_five_tabs_exist(app):
    assert [tab.label for tab in app.tabs] == TAB_LABELS


def test_changing_property_does_not_raise(app):
    for prop in config.NUMERIC_COLUMNS:
        app.sidebar.selectbox[0].select(prop).run()
        assert not app.exception


def test_manual_power_and_outlier_checkbox_do_not_raise(app):
    app.sidebar.radio[1].set_value("Manual").run()
    app.sidebar.slider[0].set_value(3.5).run()
    app.sidebar.checkbox[0].uncheck().run()
    assert not app.exception
    # Switch to Auto and back: the manual power is remembered in session_state.
    app.sidebar.radio[1].set_value("Auto (cross-validation)").run()
    app.sidebar.radio[1].set_value("Manual").run()
    assert app.sidebar.slider[0].value == 3.5


def test_upload_mode_without_file_shows_info_not_error(app):
    app.sidebar.radio[0].set_value("Upload CSV").run()
    assert not app.exception
    assert app.info


@pytest.mark.parametrize("power_mode", ["Auto (cross-validation)", "Manual"])
@pytest.mark.parametrize("exclude", [True, False])
def test_maps_tab_renders_for_every_property_and_setting(app, power_mode, exclude):
    app.sidebar.radio[1].set_value(power_mode).run()
    if not exclude:
        app.sidebar.checkbox[0].uncheck().run()
    for prop in config.NUMERIC_COLUMNS:
        app.sidebar.selectbox[0].select(prop).run()
        assert not app.exception
        assert not app.error


def test_no_figures_left_open_after_app_runs():
    plt.close("all")
    app = AppTest.from_file("../app.py", default_timeout=60).run()
    app.sidebar.selectbox[0].select("salinity").run()
    assert not app.exception
    assert plt.get_fignums() == []
