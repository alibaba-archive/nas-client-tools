#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2019-2020 Alibaba Group Holding Limited

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
from optparse import OptionParser

SIZE_63KB = 63 * 1024
SIZE_79GB = 79 * 1024 * 1024 * 1024
SIZE_900GB = 900 * 1024 * 1024 * 1024
SIZE_30TB = 30 * 1024 * 1024 * 1024 * 1024
# Exeeded max file size which is 32TB.
SIZE_60TB = 60 * 1024 * 1024 * 1024 * 1024
TIME_TO_DAY = 24 * 3600

NAMES_OF_TIMES = ["Mtime", "Atime"]
SIZES_OF_FILES = [SIZE_63KB, SIZE_79GB, SIZE_900GB, SIZE_30TB]
NAMES_OF_FILES = ["Size63KB", "Size79GB", "Size900GB", "Size30TB"]
DAYS_OF_COLDNESS = [0, 7, 14, 30, 60, 90]
NAMES_OF_COLDNESS = ["Hot", "7-Days-Cold", "14-Days-Cold",
                     "30-Days-Cold", "60-Days-Cold", "90-Days-Cold"]


def create_coldness_data(target_dir):
    if (os.path.exists(target_dir)):
        shutil.rmtree(target_dir, ignore_errors=True)
    os.mkdir(target_dir)

    for k in range(len(NAMES_OF_TIMES)):
        for i in range(len(DAYS_OF_COLDNESS)):
            curr_dir = "%s\%s_%s" % (
                target_dir, NAMES_OF_TIMES[k], NAMES_OF_COLDNESS[i])
            os.mkdir(curr_dir)
            for j in range(len(SIZES_OF_FILES)):
                curr_file = "%s\%s" % (curr_dir, NAMES_OF_FILES[j])
                f = open(curr_file, "wb+")
                f.seek(SIZES_OF_FILES[j])
                f.write(b"\0")
                f.close()
                stat = os.stat(curr_file)
                mtime = stat.st_mtime
                atime = stat.st_atime
                if (k == 0):
                    mtime = mtime - TIME_TO_DAY * DAYS_OF_COLDNESS[i]
                else:
                    atime = atime - TIME_TO_DAY * DAYS_OF_COLDNESS[i]
                os.utime(curr_file, (atime, mtime))


if __name__ == "__main__":
    parser = OptionParser("Usage: %prog [options] ")
    parser.add_option("--target_dir", dest="target_dir",
                      help="target directory to create files", default=".\simple_coldness_data")
    options, args = parser.parse_args()

    create_coldness_data(options.target_dir)
