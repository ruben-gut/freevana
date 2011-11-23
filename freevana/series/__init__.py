#!/usr/bin/env python
"""
Freevana Series
"""
__author__ = "Tirino"

# pylint: disable-msg=W0105

# Series tables
"""
CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT, url TEXT);

CREATE TABLE series_seasons (id INTEGER PRIMARY KEY AUTOINCREMENT, 
series_id INTEGER, number INTEGER, name TEXT, finished INTEGER);

CREATE TABLE series_episodes (id INTEGER PRIMARY KEY, 
season_id INTEGER, number TEXT, short_name TEXT, name TEXT, 
url TEXT, subs INTEGER, sources INTEGER);

CREATE TABLE series_episode_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, 
series_episode_id INTEGER, source TEXT, definition TEXT, audio TEXT, url TEXT);
"""

# system
import os
import re
import sys
import json
import time
import urllib
# third party
import mechanize
from BeautifulSoup import BeautifulSoup
# own
import freevana
from freevana.utils import get_item_id, titlecase, remove_bom

MEDIA_LIST_URL = 'http://www.cuevana.tv/web/series?&todas'
MEDIA_PATTERN = '\$\(\'#list\'\)\.list\(\{l:\[(.*)\], page'

SEASONS_URL_PATTERN = 'http://www.cuevana.tv/web/series?&%s&'
SEASONS_PATTERN = '\$\(\'#temporadas\'\)\.serieList\(\{l:(.*),e:'

MEDIA_SOURCES_URL_PATTERN = '%s%s' % ('http://www.cuevana.tv/player/sources',
                                                        '?id=%s&tipo=serie')
SUBTITLES_LOCATION = './subtitles/series'
SUBTITLES_URL_PATTERN = 'http://sc.cuevana.tv/files/s/sub/%s_%s.srt'

SKIP_IMG_TEXT = '[IMG]'

# pylint: disable-msg=W0703
class SeriesUpdater(freevana.Freevana):
    """
    Class for updating the freevana series database.
    """
    def __init__(self):
        freevana.Freevana.__init__(self)
        self.finished_listing_series = False
        self.finished_listing_seasons = False
        self.finished_listing_episodes = False
        self.processed_series = []
        self.no_sources_episodes = []

    def update_series_list(self):
        """
        Download the list of series and saves them to the DB
        """
        if (self.finished_listing_series):
            print "All current series already processed... skipping..."
            return

        print "***** Starting to list series... *****"

        # Obtain list of series
        data = self.browser.open(MEDIA_LIST_URL)
        soup = BeautifulSoup(data.read())
        script_data = soup.find('script')

        all_series = []
        match = re.search(MEDIA_PATTERN, str(script_data))
        if (match):
            series_json = '[%s]' % match.group(1)
            all_series = json.loads(series_json)

        for series in all_series:
            print "Adding Series ID %s, Name: %s" % (series['id'],
                                                series['tit'])
            self.add_series(series)

        self.finished_listing_series = True

    def add_series(self, series):
        """
        Given a series data, add it to the database
        """
        if self._series_exists(series['id']):
            print ">> Series already added: %s" % series['tit']
            return

        data = (series['id'], series['tit'].strip(), series['url'])
        query  = 'INSERT INTO series (id, name, url) VALUES (?, ?, ?)'
        try:
            self.execute_query(query, data)
        except Exception, ex:
            print "Could not add #%s, %s, because: %s" % (series['id'],
                                                        series['tit'], ex)
            raise ex # propagate the exception

    def _series_exists(self, series_id):
        """
        Check if a series already exists in the DB
        """
        try:
            query = 'SELECT id FROM series WHERE id=%s LIMIT 1' % series_id
            result = self.run_query(query, as_list=True)
            return (len(result) > 0)
        except Exception, ex:
            print "Couldn't check if the series exists: %s" % ex
            raise ex # propagate the exception

    def update_seasons(self):
        """
        Update the list of seasons for all series
        """
        if (self.finished_listing_seasons):
            print "All current seasons already processed... skipping..."
            return

        print "***** Start updating seasons... *****"
        query = 'SELECT id, name FROM series'
        all_series = self.run_query(query, as_list=True)
        print "ALREADY PROCESSED: %s" % self.processed_series
        for series in all_series:
            (series_id, series_name) = series
            if (series_id not in self.processed_series):
                url = SEASONS_URL_PATTERN % series_id
                try:
                    print "\nSeasons for #%s %s" % (series_id, series_name)
                    data = self.browser.open(url)
                    soup = BeautifulSoup(data.read())
                    script_data = soup.find('script')
                    match = re.search(SEASONS_PATTERN, str(script_data))
                    seasons_json = '%s' % match.group(1)
                    seasons = json.loads(seasons_json)
                    self.add_seasons(series_id, seasons)
                    self.processed_series.append(series_id)
                except Exception, ex:
                    print "Could not download season: %s" % ex
                    raise ex # propagate the exception
            else:
                print "Series already processed: %s" % series_name

        self.finished_listing_seasons = True

    def add_seasons(self, series_id, seasons):
        """
        Given a list of seasons, add each of them to the DB
        """
        try:
            if (isinstance(seasons, (dict))):
                for number in seasons.keys(): 
                    print "Adding Season # %s" % number
                    self.add_season(series_id, number, seasons[number])
            else:
                print "*** Seasons object is not dict, must be empty: %s" % (
                                                                    seasons)
        except Exception, ex:
            print "Could not add seasons.\n%s: %s" % (ex, seasons)
            raise ex # propagate the exception

    def add_season(self, series_id, number, episodes):
        """
        Add a season to the DB
        """
        season_id = self._season_exists(series_id, number)
        if season_id:
            print ">> Season already added: %s with ID: %s" % (number,
                                                               season_id)
        else:
            season_name = 'Temporada %s' % number
            data = (series_id, number, season_name, 0)
            query  = 'INSERT INTO series_seasons '
            query += '(series_id, number, name, finished)'
            query += 'VALUES (?, ?, ?, ?)'
            try:
                (_, season_id) = self.execute_query(query, data)
            except Exception, ex:
                print "Could not add season #%s, %s, because: %s" % (season_id,
                                                            season_name, ex)
                raise ex # propagate the exception

        # Add episodes
        if (season_id):
            print "Adding Episodes for Season Id %s" % season_id
            try:
                self.add_episodes(season_id, episodes)
            except Exception, ex:
                print "Could not add episodes for #%s, because: %s" % (
                                                            season_id, ex)
                raise ex # propagate the exception
        else:
            print "Something went wrong. No Season ID for: %s" % (number)

    def _season_exists(self, series_id, number):
        """
        Check if a season already exists in the DB and if it does, return id
        """
        result = False
        try:
            query  = 'SELECT id FROM series_seasons '
            query += 'WHERE number=? AND series_id=? LIMIT 1'
            rows = self.run_query(query, (number, series_id), as_list=True)
            if (rows and len(rows) > 0):
                result = rows[0][0]
        except Exception, ex:
            print "Couldn't check if the season exists: %s" % ex
            raise ex # propagate the exception
        return result

    def add_episodes(self, season_id, episodes):
        """
        Given a list of episodes, add each of them to the DB.
        """
        try:
            for episode in episodes:
                episode_id = episode['id']
                number = episode['num']
                episode_name = episode['tit'].strip()
                url = episode['url']
                print "Adding Episode ID %s, Nbr: %s Name: %s" % (
                                        episode_id, number, episode_name)
                self.add_episode(season_id, episode_id, number, url, 
                                                        episode_name)
        except Exception, ex:
            print "Could not add episodes: %s" % ex
            raise ex # propagate the exception

    def add_episode(self, season_id, episode_id, number, url, episode_name):
        """
        Add an episode to the DB
        """
        if self._episode_exists(season_id, episode_id):
            print ">> Episode already added: %s" % episode_name
            return

        data = (episode_id, season_id, number, episode_name, 
                episode_name, url, 0, 0)
        query  = 'INSERT INTO series_episodes '
        query += '(id, season_id, number, short_name, name, url, subs, '
        query += 'sources) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        try:
            self.execute_query(query, data)
        except Exception, ex:
            print "Could not add episode #%s, %s, because: %s" % (episode_id,
                                                            episode_name, ex)
            raise ex # propagate the exception

    def _episode_exists(self, season_id, episode_id):
        """
        Check if a series already exists in the DB
        """
        try:
            query  = 'SELECT id, season_id FROM series_episodes WHERE id=?'
            result = self.run_query(query, (episode_id,), as_list=True)
            exists = (len(result) > 0)
            if (exists):
                (_id, seas_id) = result[0]
                if (seas_id != season_id):
                    print "WARNING: ****** Episode changed season!!! "
                    print "WARNING: ****** Old Season: %s, New Season: %s" % (
                                                        seas_id, season_id)
            return exists
        except Exception, ex:
            print "Couldn't check if the episode exists: %s" % ex
            raise ex # propagate the exception


    def process_sources(self):
        """
        Iterate the list of episodes from the DB and get the
        sources of those that don't have them yet
        """
        print "***** Start downloading sources... *****"
        try:
            query  = 'SELECT id, short_name FROM series_episodes '
            query += 'WHERE sources=0 ORDER BY id'
            episodes = self.run_query(query, as_list=True)

            print "NO SOURCES: %s" % self.no_sources_episodes
            for episode in episodes:
                (episode_id, episode_name) = episode
                if (episode_id not in self.no_sources_episodes):
                    url  = MEDIA_SOURCES_URL_PATTERN % episode_id
                    print "Sources for #%s %s" % (episode_id, episode_name)
                    data = self.browser.open(url)
                    source_data = self.get_sources(BeautifulSoup(data.read()))
                    if (source_data):
                        count = self.handle_sources(source_data, 'serie', url,
                                                episode_id, self.save_source)
                        # don't mark srcs as downloaded if we had none
                        if (count > 0):
                            self.mark_sources_as_downloaded(episode_id)
                    else:
                        self.no_sources_episodes.append(episode_id)

                    time.sleep(freevana.REQUEST_SLEEP_TIME)
                else:
                    print "Episode had no sources: %s" % episode_name
        except Exception, ex:
            print "Coudln't download sources: %s" % ex
            raise ex # propagate exception

    def save_source(self, episode_id, source, definition, audio, url):
        """
        Save source information into the DB.
        """
        try:
            query  = 'INSERT INTO series_episode_sources '
            query += '(series_episode_id, source, definition, audio, url) '
            query += 'VALUES (?, ?, ?, ?, ?)'
            data = (episode_id, source, definition, audio, url)
            self.execute_query(query, data)
            print "Added source for Episode ID: %s, Source: %s, Link: %s" % (
                                                    episode_id, source, url)
        except Exception, ex:
            print "Couldn't save the source: %s" % ex
            raise ex # propagate the exception

    def mark_sources_as_downloaded(self, episode_id):
        """
        Update the DB marking the movie sources as 'downloaded'.
        """
        try:
            data = (1, episode_id)
            query = 'UPDATE series_episodes SET sources=? WHERE id=?'
            self.execute_query(query, data)
        except Exception, ex:
            print "Couldn't mark sources as downloaded: %s" % ex
            raise ex


    def download_subtitles(self):
        """
        Download the subtitles for all episodes that need it.
        """
        print "***** Start downloading subtitles... *****"
        try:
            query = 'SELECT id, short_name FROM series_episodes WHERE subs=0'
            episodes = self.run_query(query, as_list=True)
            for episode in episodes:
                (episode_id, episode_name) = episode
                for lang in freevana.SUBTITLES_LANGUAGES:
                    if (not self._subtitle_exists(episode_id, lang)):
                        print "Downloading subs for #%s - %s in %s" % (
                                            episode_id, episode_name, lang)
                        self.download_subtitle(episode_id, lang)
                        time.sleep(freevana.SUBTITLES_SLEEP_TIME)
                self.mark_subs_as_downloaded(episode_id)
        except Exception, ex:
            print "Could not download subtitles: %s" % ex
            raise ex # propagate the exception

    def _subtitle_exists(self, episode_id, lang):
        """
        Check if a subtitle already exists
        """
        filename = "%s/%s_%s.srt" % ( "%s/%s" % (SUBTITLES_LOCATION, lang),
                                                        episode_id, lang)
        return os.path.exists(filename)

    def download_subtitle(self, episode_id, lang):
        """
        Download a Subtitle in a specific language
        """
        try:
            url = SUBTITLES_URL_PATTERN % (episode_id, lang)
            self.browser.retrieve(url, filename="%s/%s_%s.srt" % (
                            "%s/%s" % (SUBTITLES_LOCATION, lang),
                            episode_id, lang))
        except KeyboardInterrupt, ex:
            print ex
            sys.exit(0)
        except Exception, ex:
            new_ex = freevana.parse_exception(ex, url)
            if (isinstance(new_ex, freevana.FileNotFoundException)):
                # this one is ok to happen, we guess (for now)
                print 'No subtitle in %s. %s' % (lang, new_ex)
            else:
                raise new_ex # propagate the exception

    def mark_subs_as_downloaded(self, episode_id):
        """
        Update the DB marking the episode's subs as downloaded.
        """
        try:
            data = (1, episode_id)
            query = 'UPDATE series_episodes SET subs=? WHERE id=?'
            self.execute_query(query, data)
        except Exception, ex:
            print "Couldn't mark subs as downloaded: %s" % ex
            raise ex # propagate the exception

"""
Note: episode names are only saved in their "short" version
      this means that some names might be truncated.
      This is because downloading the full names requires
      accessing an extra HTML page for each episode which
      would greatly increase the http usage and don't really
      provide any extra functionality.
      Because of this, episode names are saved in the 'short_name'
      column leaving the 'name' column empty for now.
      We might add support for downloading full names later.
"""