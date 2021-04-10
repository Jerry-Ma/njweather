#!/usr/bin/env python

import logging
import logging.config
from fake_useragent import UserAgent
import urllib.parse
import requests
# import re
# from bs4 import BeautifulSoup
import pandas as pd
# import json
from datetime import datetime


class NjWeatherQuery(object):

    _ua = UserAgent()
    _baseurl = "https://www.njweather.org/data"

    _query_template = 'startDate={date_start}&endDate={date_end}&formSubmitted=1&selectedElements%5B%5D=1&selectedElements%5B%5D=2&selectedElements%5B%5D=5&selectedElements%5B%5D=4&selectedElements%5B%5D=1037&selectedElements%5B%5D=3&selectedElements%5B%5D=6&selectedElements%5B%5D=7&selectedElements%5B%5D=15&selectedStations%5B%5D={site_id}'  # noqa: E501

    _site_id_map = {
            'Jersey City': 3411,
            }

    logger = logging.getLogger('njweatherquery')

    @classmethod
    def get_site_id(cls, site):
        if site not in cls._site_id_map:
            raise ValueError(
                    f"site {site} not in {list(cls._site_id_map.keys())}")
        site_id = cls._site_id_map[site]
        return site_id

    def __init__(self, site):
        s = self._session = requests.Session()
        s.headers.update({
                    'User-Agent': self._ua.random
                    })
        self._site_id = self.get_site_id(site)

    @staticmethod
    def parse_response(response):
        # print(response.text)
        df = pd.read_html(response.text, attrs={'id': 'dataout'})[0]
        # post-process the date column
        df['date'] = df['Eastern Time'].apply(pd.to_datetime)
        df = df.sort_values(by=['date'])
        print(df)
        return df

    @staticmethod
    def _pprint_df(df):
        return (
                f"{len(df)} records "
                f"from {df['date'].iloc[-1]} "
                f"to {df['date'].iloc[0]}")

    def get_data_by_datetime(self, start, end):
        # check date to get start df
        date_start = datetime.fromisoformat(start)
        date_end = datetime.fromisoformat(end)
        if date_end <= date_start:
            raise ValueError('invalid date range')

        s = self._session
        s.cookies.clear()
        url = '{}?{}'.format(
                self._baseurl,
                self._query_template.format(
                    date_start=urllib.parse.quote_plus(
                        date_start.strftime('%Y-%m-%d %H:%M')
                        ),
                    date_end=urllib.parse.quote_plus(
                        date_end.strftime('%Y-%m-%d %H:%M')
                        ),
                    site_id=self._site_id
                ))
        r = s.post(url)
        df = self.parse_response(r)
        self.logger.debug(f"finish download {self._pprint_df(df)}")
        return df


class NjWeather(object):

    _ua = UserAgent()
    _baseurl = "https://www.njweather.org/data"

    _valid_cadences = ['5min', 'hourly', 'daily']
    _valid_offset_units = ['month', 'day', 'hour']
    _site_id_map = {
            'Jersey City': 3411,
            }

    logger = logging.getLogger('njweather')

    @classmethod
    def get_initial_query_url(cls, cadence, site):
        if cadence not in cls._valid_cadences:
            raise ValueError(
                    f"cadence {cadence} not in {cls._valid_cadences}")
        if site not in cls._site_id_map:
            raise ValueError(
                    f"site {site} not in {list(cls._site_id_map.keys())}")
        site_id = cls._site_id_map[site]
        url = f"{cls._baseurl}/{cadence}/{site_id}"
        cls.logger.debug(f"query {url} for cadence={cadence} site={site}")
        return url

    @classmethod
    def get_offset_query_url(cls, value, unit):
        value = int(value)
        if unit not in cls._valid_offset_units:
            raise ValueError(
                    f"unit {unit} not in {cls._valid_offset_units}")
        if value > 0:
            verb = 'add'
        else:
            verb = 'sub'
        url = f"{cls._baseurl}/{verb}/{abs(value)}/{unit}"
        cls.logger.debug(f"query offset {url} for value={value} unit={unit}")
        return url

    def __init__(self, cadence, site):
        s = self._session = requests.Session()
        s.headers.update({
                    'User-Agent': self._ua.random
                    })
        self._initial_query_url = self.get_initial_query_url(cadence, site)

    @staticmethod
    def parse_response(response):
        return NjWeatherQuery.parse_response(response)
        # soup = BeautifulSoup(response.text, 'lxml')
        # pattern = re.compile(r'\"aaData\"\s*:\s*(\[[.\s\S]*?\])')
        # scripts = soup.find_all('script')
        # data_json = None
        # for script in scripts:
        #     if script.string is None:
        #         continue
        #     # print(script.string)
        #     m = pattern.search(script.string)
        #     if m:
        #         data_json = m.group(1)
        #         break
        # else:
        #     return None
        # df = pd.DataFrame.from_records(json.loads(data_json))
        # # post-process the date column
        # # print(df)
        # df['date'] = df['date'].apply(pd.to_datetime)
        # return df

    @staticmethod
    def _pprint_df(df):
        return (
                f"{len(df)} records "
                f"from {df['date'].iloc[-1]} "
                f"to {df['date'].iloc[0]}")

    def get_data_by_datetime(self, start, end):
        # make init query
        s = self._session
        s.cookies.clear()
        r_init = s.get(self._initial_query_url)
        # self.logger.debug(f'{q.cookies}')
        df_init = self.parse_response(r_init)

        # check date to get start df
        date_start = datetime.fromisoformat(start)
        date_end = datetime.fromisoformat(end)
        # we assume the data is sorted already.
        # find out if we have end date captured
        if date_end > df_init['date'].iloc[0]:
            self.logger.warning(
                "the end date seems to be at future which data may not exists."
                )
        if date_end < df_init['date'].iloc[-1]:
            # we need to compute a delta days to replace the initial query
            init_offset = (date_end - df_init['date'].iloc[-1])
            r_start = s.get(
                    self.get_offset_query_url(
                        init_offset.total_seconds() / (24 * 60 * 60), 'day'))
            df_start = self.parse_response(r_start)
        else:
            r_start = r_init
            df_start = df_init

        # now we can keep -1 day to search through the range
        day_span = int(abs(
                (date_end - date_start).total_seconds() / (24 * 60 * 60)))
        dfs = [df_start, ]
        self.logger.debug(f"init with {self._pprint_df(df_start)}")
        for i in range(day_span):
            r_step = s.get(
                    self.get_offset_query_url(
                        -1, 'day'
                        )
                    )
            # the extra slice is to avoid the duplicate of the latest
            # entry
            df_step = self.parse_response(r_step).iloc[1:]
            self.logger.debug(f"append {self._pprint_df(df_step)}")
            dfs.append(df_step)
        df = pd.concat(dfs)
        df = df.sort_values(by=['date'])
        self.logger.debug(f"finish download {self._pprint_df(df)}")
        return df


def init_log():

    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'short': {
                'format': '[%(levelname)s] %(name)s: %(message)s'
                },
            },
        'handlers': {
            'default': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'short',
                },
            },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': 'DEBUG',
                'propagate': False
                },
            }
        }
    logging.config.dictConfig(config)


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="Download data from NJWeather.")

    parser.add_argument(
            '--cadence', '-c',
            default='5min',
            help="The data cadence",
            choices=NjWeather._valid_cadences)
    parser.add_argument(
            '--site', '-s',
            default='Jersey City',
            help="The site",
            choices=list(NjWeather._site_id_map.keys()))
    parser.add_argument(
            '--date', '-d',
            nargs=2,
            required=True,
            help="The date range, specified as <start> <end>",
            )
    parser.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Suppress the debug messages.'
            )

    option = parser.parse_args()

    if not option.quiet:
        init_log()

    cadence = option.cadence
    site = option.site

    start = option.date[0]
    end = option.date[1]

    logger = logging.getLogger()

    # njw = NjWeatherQuery(site=site)
    njw = NjWeather(cadence=cadence, site=site)

    df = njw.get_data_by_datetime(start, end)

    outname = f'njw_{cadence}_{site.replace(" ", "_")}_{start}-{end}.csv'
    df.to_csv(
            f'njw_{cadence}_{site.replace(" ", "_")}_{start}-{end}.csv',
            index=False)
    logger.debug(f"{len(df)} records saved in {outname}")
