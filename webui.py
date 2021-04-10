#! /usr/bin/env python


from tollan.utils.fmt import pformat_yaml
from dasha.web.templates import ComponentTemplate
from dasha.web.templates.common import LabeledDropdown
from dash_table import DataTable
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input, State
from datetime import date
import cachetools.func

import sys
from pathlib import Path
# make available the repo folder as a package
sys.path.insert(0, Path(__file__).parent.parent.as_posix())
from njweather import njweather  # noqa: E402

njw_cls = njweather.NjWeather


@cachetools.func.ttl_cache(maxsize=None, ttl=600)
def get_njw_data(cadence, site, date_start, date_end):
    njw = njw_cls(cadence=cadence, site=site)
    df = njw.get_data_by_datetime(date_start, date_end)
    return df


def get_site_options():
    site_id_map = njw_cls._site_id_map
    return [{
        'label': k,
        'value': k
            } for k, v in site_id_map.items()]


class NjWeatherWeb(ComponentTemplate):
    _component_cls = dbc.Container

    _title_text = "NJ Weather Exporter"

    def setup_layout(self, app):
        container = self
        header, body = container.grid(2, 1)
        header.className = 'mt-4'
        header.children = [
                html.H2(self._title_text),
                html.Hr()
                ]
        controls_container, output_container = body.grid(2, 1)
        controls_form = controls_container.child(
                dbc.Form, inline=True)

        site_options = get_site_options()
        site_drp = controls_form.child(LabeledDropdown(
            label_text='Site',
            style={
                'height': '48px',
                },
            dropdown_props={
                'options': site_options,
                'value': site_options[0]['value'],
                'style': {
                    'height': '48px',
                    }
                },
            className='mr-4',
            )).dropdown

        date_range_picker = controls_form.child(
                dcc.DatePickerRange,
                min_date_allowed=date(2020, 1, 1),
                max_date_allowed=date(2030, 1, 1),
                # with_portal=True,
                className='mr-4'
                )
        exec_btn = controls_form.child(
                dcc.Loading).child(
                dbc.Button,
                "Run", color="success",
                style={'height': '48px', 'width': '128px'})

        output_container.className = 'mt-4'
        output_dt = output_container.child(
                DataTable,
                export_format="csv",
                style_cell={
                    'padding': '0.5em',
                    'width': '0px',
                    },
                css=[
                    {
                        'selector': (
                            '.dash-spreadsheet-container '
                            '.dash-spreadsheet-inner *, '
                            '.dash-spreadsheet-container '
                            '.dash-spreadsheet-inner *:after, '
                            '.dash-spreadsheet-container '
                            '.dash-spreadsheet-inner *:before'),
                        'rule': 'box-sizing: inherit; width: 100%;'
                        }
                    ],
                )

        super().setup_layout(app)

        @app.callback(
            [
                Output(date_range_picker.id, 'initial_visible_month'),
                Output(date_range_picker.id, 'start_date'),
                Output(date_range_picker.id, 'end_date'),
                ],
            [
                Input(date_range_picker.id, 'id'),
                ],
            )
        def update_date_range_picker_init(*args):
            d = date.today()
            m = date(d.year, d.month, 1)
            initial_visible_month = m
            start_date = m
            end_date = d
            return initial_visible_month, start_date, end_date

        @app.callback(
            [
                Output(exec_btn.id, 'text'),
                Output(output_dt.id, 'columns'),
                Output(output_dt.id, 'data'),
                ],
            [
                Input(exec_btn.id, 'n_clicks'),
                ],
            [
                State(exec_btn.id, 'text'),
                State(site_drp.id, 'value'),
                State(date_range_picker.id, 'start_date'),
                State(date_range_picker.id, 'end_date')
                ],
            prevent_initial_call=True
            )
        def update_df(
                n_clicks, btn_text, site_drp_value, date_start, date_end):
            df = get_njw_data(
                    cadence='5min', site=site_drp_value,
                    date_start=date_start, date_end=date_end)
            data = df.to_dict('record')
            columns = [
                    {
                        'label': c,
                        'id': c
                        }
                    for c in df.columns
                    ]
            return btn_text, columns, data


dasha_config = {
        "title_text": NjWeatherWeb._title_text,
        "template": NjWeatherWeb,
        'EXTERNAL_STYLESHEETS': [
            # dbc.themes.MATERIA,
            # dbc.themes.YETI,
            dbc.themes.BOOTSTRAP,
            ],
        'ASSETS_IGNORE': 'bootstrap.*'
        }

# site runtime
_dasha_ext_module_parent = 'dasha.web.extensions'
extensions = [
    {
        'module': f'{_dasha_ext_module_parent}.dasha',
        'config': dasha_config,
        },
    ]
