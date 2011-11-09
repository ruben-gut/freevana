#!/usr/bin/env python
from freevana import TemporaryErrorException
from freevana.series import SeriesUpdater

def main():
    """
    Entry point
    """
    updater = SeriesUpdater()
    loop = True
    while (loop):
        try:
            updater.update_series_list()
            updater.update_seasons()
            updater.update_episodes()
            updater.process_sources()
            updater.download_subtitles()
            loop = False
        except KeyboardInterrupt, ex:
            print "Aborting... "
            return
        except TemporaryErrorException, ex:
            print "Series site is temporary down. Will retry..."
        except Exception, ex:
            print "An unexpected error ocurred. Will retry... "
            print "(Error was: %s)" % str(ex)

if (__name__ == '__main__'):
    main()
