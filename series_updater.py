#!/usr/bin/env python
__author__ = "Tirino"

# if you have issues running this on Linux, try this before running:
# export PYTHONIOENCODING=utf-8

import traceback
import time

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
            updater.process_sources()
            updater.download_subtitles()
            loop = False
        except KeyboardInterrupt, ex:
            print "Aborting... "
            return
        except TemporaryErrorException, ex:
            print "Series site is temporary down. Will retry..."
            time.sleep(2.5)
        except Exception, ex:
            print "An unexpected error occurred. Will retry... "
            print "(Error was: %s)" % unicode(ex)
            traceback.print_exc()
            time.sleep(1.5)

if (__name__ == '__main__'):
    main()
