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
import sys
import shutil
import logging
import datetime
from optparse import OptionParser
from collections import OrderedDict
try:
    import json
except:
    # load simplejson instead if python version is too old
    import simplejson as json

LOG_FILENAME = 'analyze_data_coldness.log'

files = os.listdir(".")
for fname in files:
    if (fname.startswith(LOG_FILENAME)):
        os.remove(fname)

logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(pathname)s:%(lineno)d %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


SIZE_64KB = 64 * 1024
TIME_TO_DAY = 24 * 3600
PATH = "Path"
MTIME = "Mtime"
ATIME = "Atime"
SIZE = "Size"
COUNT = "Count"
COUNT_RATIO = "CountRatio"
SIZE_RATIO = "SizeRatio"
SORT_KEYS = [SIZE, SIZE_RATIO, COUNT, COUNT_RATIO]
VALID_SIZE = SIZE_64KB
VALID_SIZE_STR = ">=64KB"
NAMES_OF_TIMES = [MTIME, ATIME]
DAYS_OF_COLDNESS = [0, 7, 14, 30, 60, 90]
NAMES_OF_COLDNESS = ["Hot", "7-Days-Cold", "14-Days-Cold",
                     "30-Days-Cold", "60-Days-Cold", "90-Days-Cold"]
SIZE_1B = 1
SIZE_1KB = 1024
SIZE_1MB = 1024 * 1024
SIZE_1GB = 1024 * 1024 * 1024
SIZE_1TB = 1024 * 1024 * 1024 * 1024
SIZE_1PB = 1024 * 1024 * 1024 * 1024 * 1024
SIZE_LIST = [SIZE_1PB, SIZE_1TB, SIZE_1GB, SIZE_1MB, SIZE_1KB, SIZE_1B]
SIZE_UNIT_LIST = ["PB", "TB", "GB", "MB", "KB", "B"]
COUNT_1 = 1
COUNT_K = 1000
COUNT_M = 1000 * 1000
COUNT_B = 1000 * 1000 * 1000
COUNT_T = 1000 * 1000 * 1000 * 1000
COUNT_LIST = [COUNT_T, COUNT_B, COUNT_M, COUNT_K, COUNT_1]
COUNT_UNIT_LIST = ["T", "B", "M", "K", ""]


def count_to_str(count):
    count_f = float(count)
    for i in range(len(COUNT_LIST)):
        if (count_f >= COUNT_LIST[i]):
            if (COUNT_LIST[i] == COUNT_1):
                return "{:.0f}".format(count_f / COUNT_LIST[i])
            else:
                return "{:.2f}".format(count_f / COUNT_LIST[i]) + " " + COUNT_UNIT_LIST[i]
    return str(count)


def size_to_str(data):
    data_f = float(data)
    for i in range(len(SIZE_LIST)):
        if (data_f >= SIZE_LIST[i]):
            return "{:.2f}".format(data_f / SIZE_LIST[i]) + " " + SIZE_UNIT_LIST[i]
    return str(data)


def ratio_to_str(ratio):
    return "{:.0f}".format(float(ratio) * 100) + "%"


def parse_tiering_policies(tiering_policies_str, tiering_policies, error_msg):
    policies = tiering_policies_str.split(",")
    if (len(policies) == 0):
        error_msg = 'len((%s).split(",")) is 0' % (tiering_policies_str)
        logging.error(error_msg)
        return False
    for policy in policies:
        parts = policy.split("-")
        if (not len(parts) == 2):
            error_msg = 'len((%s).split(",")): %s is not 2' % (
                policy, len(parts))
            logging.error(error_msg)
            return False
        try:
            parts[0] = str(int(parts[0]))
            tiering_policy = [parts[0]]
            parts[1] = parts[1].lower()
            if (parts[1] == MTIME.lower()):
                tiering_policy.append(MTIME)
            elif (parts[1] == ATIME.lower()):
                tiering_policy.append(ATIME)
            else:
                error_msg = 'parts[1]: %s is not MTIME or ATIME' % parts[1]
                return False
            tiering_policies.append(tiering_policy)
        except:
            error_msg = 'parts[0]: %s cannot be converted to int' % parts[0]
            return False
    return True


def rank_dir_stats(all_level_stats, top_n=2, sort_key=SIZE):
    result = OrderedDict()
    for l in all_level_stats.keys():
        for policy in tiering_policies:
            key = "%s#%s#%s#%s" % (
                policy[1], policy[0], sort_key, VALID_SIZE_STR)
            ordered = OrderedDict(sorted(all_level_stats[l].items(
            ), key=lambda x: -x[1][key]))  # reversed sort of size
            logging.debug(
                "ordered by key:%s, all_level_stats[level:%d]: %s" % (key, l, ordered))
            i = 0
            for path in ordered.keys():
                if (i >= top_n):
                    i = 0
                    break
                level = "level-%d" % l
                if (not level in result):
                    result[level] = OrderedDict()
                rkey = "Rank#%s#%s#%s" % (str(i), policy[1], policy[0])
                result[level][rkey] = OrderedDict()
                result[level][rkey][PATH] = path
                result[level][rkey][SIZE] = size_to_str(ordered[path][SIZE])
                key = "%s#%s" % (SIZE, VALID_SIZE_STR)
                result[level][rkey][key] = size_to_str(ordered[path][key])
                key = "%s#%s#%s#%s" % (
                    policy[1], policy[0], SIZE, VALID_SIZE_STR)
                result[level][rkey][key] = size_to_str(ordered[path][key])
                key = "%s#%s#%s#%s" % (
                    policy[1], policy[0], SIZE_RATIO, VALID_SIZE_STR)
                result[level][rkey][key] = ratio_to_str(ordered[path][key])
                result[level][rkey][COUNT] = count_to_str(ordered[path][COUNT])
                key = "%s#%s" % (COUNT, VALID_SIZE_STR)
                result[level][rkey][key] = count_to_str(ordered[path][key])
                key = "%s#%s#%s#%s" % (
                    policy[1], policy[0], COUNT, VALID_SIZE_STR)
                result[level][rkey][key] = count_to_str(ordered[path][key])
                key = "%s#%s#%s#%s" % (
                    policy[1], policy[0], COUNT_RATIO, VALID_SIZE_STR)
                result[level][rkey][key] = ratio_to_str(ordered[path][key])
                i = i + 1
                logging.debug("i:%d, level:%s, rkey:%s, result[level][rkey]:%s" % (
                    i, level, rkey, result[level][rkey]))
    return json.dumps(result, indent=4)


def init_dir_stats():
    dir_stats = {}
    dir_stats[COUNT] = 0
    dir_stats[SIZE] = 0
    key = "%s#%s" % (COUNT, VALID_SIZE_STR)
    dir_stats[key] = 0
    key = "%s#%s" % (SIZE, VALID_SIZE_STR)
    dir_stats[key] = 0
    key = "%s#%s" % (COUNT_RATIO, VALID_SIZE_STR)
    dir_stats[key] = 0
    key = "%s#%s" % (SIZE_RATIO, VALID_SIZE_STR)
    dir_stats[key] = 0
    for policy in tiering_policies:
        key = "%s#%s#%s#%s" % (policy[1], policy[0], COUNT, VALID_SIZE_STR)
        dir_stats[key] = 0
        key = "%s#%s#%s#%s" % (policy[1], policy[0], SIZE, VALID_SIZE_STR)
        dir_stats[key] = 0
        key = "%s#%s#%s#%s" % (
            policy[1], policy[0], COUNT_RATIO, VALID_SIZE_STR)
        dir_stats[key] = 0
        key = "%s#%s#%s#%s" % (
            policy[1], policy[0], SIZE_RATIO, VALID_SIZE_STR)
        dir_stats[key] = 0
    return dir_stats


def add_dir_stats(dir_stats1, dir_stats2):
    dir_stats1[COUNT] = dir_stats1[COUNT] + dir_stats2[COUNT]
    dir_stats1[SIZE] = dir_stats1[SIZE] + dir_stats2[SIZE]
    key = "%s#%s" % (COUNT, VALID_SIZE_STR)
    dir_stats1[key] = dir_stats1[key] + dir_stats2[key]
    key = "%s#%s" % (SIZE, VALID_SIZE_STR)
    dir_stats1[key] = dir_stats1[key] + dir_stats2[key]
    for policy in tiering_policies:
        key = "%s#%s#%s#%s" % (policy[1], policy[0], COUNT, VALID_SIZE_STR)
        dir_stats1[key] = dir_stats1[key] + dir_stats2[key]
        key = "%s#%s#%s#%s" % (policy[1], policy[0], SIZE, VALID_SIZE_STR)
        dir_stats1[key] = dir_stats1[key] + dir_stats2[key]


def get_parent_path(curr_path):
    return os.path.abspath(os.path.join(curr_path, os.pardir))


def is_timestamp_cold(timestamp, days_to_cold):
    cold_time = datetime.datetime.now() - datetime.timedelta(days=days_to_cold)
    cold_timestamp = (
        cold_time - datetime.datetime(1970, 1, 1)).total_seconds()
    if (timestamp < cold_timestamp):
        return True
    else:
        return False


def get_ratio(dividend, divisor):
    try:
        return float(dividend) / float(divisor)
    except:
        logging.debug("failed to get_ratio %s / %s, return 0" %
                      (dividend, divisor))
        return 0


def get_volume_cold_ratio_rank(target_dir, tiering_policies, dir_levels=3, top_n=2, sort_key=SIZE):
    target_dir_stats = init_dir_stats()

    # use dfs stack to get all stats
    all_level_stats = {1: {target_dir: target_dir_stats}}
    # (start_dir_level, start_path, phase). Phase1: expanding. Phase2: collecting stats
    st = [(1, target_dir, 1)]

    while (len(st) > 0):
        (curr_level, curr_path, curr_phase) = st.pop()
        logging.debug("curr_level: %s, curr_path: %s, curr_phase: %s" %
                      (curr_level, curr_path, curr_phase))

        if (curr_level < dir_levels and curr_phase == 1):
            if (not curr_level in all_level_stats):
                all_level_stats[curr_level] = {}
            all_level_stats[curr_level][curr_path] = init_dir_stats()
            st.append((curr_level, curr_path, 2))
            new_level = curr_level + 1
            if (not os.path.isdir(curr_path)):
                continue
            try:
                children = os.listdir(curr_path)
                for child in children:
                    new_path = os.path.join(curr_path, child)
                    if (not new_level in all_level_stats):
                        all_level_stats[new_level] = {}
                    st.append((new_level, new_path, 1))
            except:
                logging.error("os.listdir(%s) failed" % curr_path)

        if (curr_level >= dir_levels and curr_phase == 1):
            if (not curr_level in all_level_stats):
                all_level_stats[curr_level] = {}
            all_level_stats[curr_level][curr_path] = init_dir_stats()
            # use bfs queue to collect stats > dir_levels
            q = [curr_path]
            while (len(q) > 0):
                curr_path2 = q.pop(0)
                try:
                    stat = os.stat(curr_path2)
                except:
                    logging.error("os.stat(%s) failed" % curr_path2)
                    continue
                size = stat.st_size
                mtime = stat.st_mtime
                atime = stat.st_atime
                all_level_stats[curr_level][curr_path][COUNT] = all_level_stats[curr_level][curr_path][COUNT] + 1
                all_level_stats[curr_level][curr_path][SIZE] = all_level_stats[curr_level][curr_path][SIZE] + size
                if (size >= VALID_SIZE):
                    key = "%s#%s" % (COUNT, VALID_SIZE_STR)
                    all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + 1
                    key = "%s#%s" % (SIZE, VALID_SIZE_STR)
                    all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + size
                    for policy in tiering_policies:
                        if ((policy[1] == MTIME and is_timestamp_cold(mtime, int(policy[0])))
                                or (policy[1] == ATIME and is_timestamp_cold(atime, int(policy[0])))):
                            key = "%s#%s#%s#%s" % (
                                policy[1], policy[0], COUNT, VALID_SIZE_STR)
                            all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + 1
                            key = "%s#%s#%s#%s" % (
                                policy[1], policy[0], SIZE, VALID_SIZE_STR)
                            all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + size

                if (not os.path.isdir(curr_path2)):
                    continue
                try:
                    children = os.listdir(curr_path2)
                    for child in children:
                        new_path2 = os.path.join(curr_path2, child)
                        q.append(new_path2)
                except:
                    logging.error("os.listdir(%s)" % curr_path2)

            parent_path = get_parent_path(curr_path)
            parent_level = curr_level - 1
            logging.debug("parent_level: %s, parent_path: %s, all_level_stats[parent_level][parent_path]: %s"
                          % (parent_level, parent_path, all_level_stats[parent_level][parent_path]))
            logging.debug("curr_level: %s, curr_path: %s, all_level_stats[curr_level][curr_path]: %s"
                          % (curr_level, curr_path, all_level_stats[curr_level][curr_path]))
            add_dir_stats(
                all_level_stats[parent_level][parent_path], all_level_stats[curr_level][curr_path])
            continue

        if (curr_phase == 2):
            try:
                stat = os.stat(curr_path)
            except:
                logging.error("os.stat(%s) failed" % curr_path)
                continue
            logging.debug("phase 2, curr_path: %s, stat: %s, all_level_stats[curr_level][curr_path]: %s" % (
                curr_path, stat, all_level_stats[curr_level][curr_path]))
            size = stat.st_size
            mtime = stat.st_mtime
            atime = stat.st_atime
            all_level_stats[curr_level][curr_path][COUNT] = all_level_stats[curr_level][curr_path][COUNT] + 1
            all_level_stats[curr_level][curr_path][SIZE] = all_level_stats[curr_level][curr_path][SIZE] + size
            if (size >= VALID_SIZE):
                key = "%s#%s" % (COUNT, VALID_SIZE_STR)
                all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + 1
                key = "%s#%s" % (SIZE, VALID_SIZE_STR)
                all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + size
                for policy in tiering_policies:
                    if ((policy[1] == MTIME and is_timestamp_cold(mtime, int(policy[0])))
                            or (policy[1] == ATIME and is_timestamp_cold(atime, int(policy[0])))):
                        key = "%s#%s#%s#%s" % (
                            policy[1], policy[0], COUNT, VALID_SIZE_STR)
                        all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + 1
                        key = "%s#%s#%s#%s" % (
                            policy[1], policy[0], SIZE, VALID_SIZE_STR)
                        all_level_stats[curr_level][curr_path][key] = all_level_stats[curr_level][curr_path][key] + size
            all_level_stats[curr_level][curr_path]["%s#%s" % (COUNT_RATIO, VALID_SIZE_STR)] = get_ratio(
                all_level_stats[curr_level][curr_path]["%s#%s" % (COUNT, VALID_SIZE_STR)], all_level_stats[curr_level][curr_path][COUNT])
            all_level_stats[curr_level][curr_path]["%s#%s" % (SIZE_RATIO, VALID_SIZE_STR)] = get_ratio(
                all_level_stats[curr_level][curr_path]["%s#%s" % (SIZE, VALID_SIZE_STR)], all_level_stats[curr_level][curr_path][SIZE])
            for policy in tiering_policies:
                all_level_stats[curr_level][curr_path]["%s#%s#%s#%s" % (policy[1], policy[0], COUNT_RATIO, VALID_SIZE_STR)] = get_ratio(
                    all_level_stats[curr_level][curr_path]["%s#%s#%s#%s" % (policy[1], policy[0], COUNT, VALID_SIZE_STR)], all_level_stats[curr_level][curr_path]["%s#%s" % (COUNT, VALID_SIZE_STR)])
                all_level_stats[curr_level][curr_path]["%s#%s#%s#%s" % (policy[1], policy[0], SIZE_RATIO, VALID_SIZE_STR)] = get_ratio(
                    all_level_stats[curr_level][curr_path]["%s#%s#%s#%s" % (policy[1], policy[0], SIZE, VALID_SIZE_STR)], all_level_stats[curr_level][curr_path]["%s#%s" % (SIZE, VALID_SIZE_STR)])
            parent_path = get_parent_path(curr_path)
            parent_level = curr_level - 1
            if (len(st) > 0):
                logging.debug("parent_level: %s, parent_path: %s, all_level_stats[parent_level][parent_path]: %s"
                              % (parent_level, parent_path, all_level_stats[parent_level][parent_path]))
                logging.debug("curr_level: %s, curr_path: %s, all_level_stats[curr_level][curr_path]: %s"
                              % (curr_level, curr_path, all_level_stats[curr_level][curr_path]))
                add_dir_stats(
                    all_level_stats[parent_level][parent_path], all_level_stats[curr_level][curr_path])

    result = rank_dir_stats(all_level_stats, top_n, sort_key)
    logging.info(result)
    return result


if __name__ == "__main__":
    parser = OptionParser("Usage (-h for help): %prog [options]")
    parser.add_option("--target_dir", dest="target_dir",
                      help="target directory to start data coldness analysis, default is current folder ./", default="./")
    parser.add_option("--dir_levels", dest="dir_levels",
                      help="levels of directories to print out, default is 3", default=3)
    parser.add_option("--tiering_policies", dest="tiering_policies",
                      help="tiering policies to rank directories. put (days, atime/mtime) like 14-atime,30-atime, or use default policy 14-atime (atime 14-day cold)", default="14-atime")
    parser.add_option("--top_n", dest="top_n",
                      help="print top N of the tiering policies of each dir level, default is 2", default=2)
    parser.add_option("--sort_key", dest="sort_key",
                      help="sort the rank by key. default is Size. Chosen from %s of data >= 64KB" % SORT_KEYS, default=SIZE)
    options, args = parser.parse_args()
    message = ''

    try:
        options.dir_levels = int(options.dir_levels)
        options.top_n = int(options.top_n)
    except:
        message = "parse options.dir_levels:%s and options.top_n:%s to int failed" % (
            options.dir_levels, options.top_n)
        logging.error(message)
        print(message)
        sys.exit(1)

    tiering_policies = []
    if (not parse_tiering_policies(options.tiering_policies, tiering_policies, message)):
        message = "parse_tiering_policies(%s, tiering_policies) failed: %s" % (
            options.tiering_policies, message)
        logging.error(message)
        print(message)
        sys.exit(1)

    if (not os.path.exists(options.target_dir)):
        message = "options.target_dir:%s doesn't exist" % options.target_dir
        logging.error(message)
        print(message)
        sys.exit(1)
    if (not os.path.isdir(options.target_dir)):
        message = "options.target_dir:%s is not a directory" % options.target_dir
        logging.error(message)
        print(message)
        sys.exit(1)
    options.target_dir = os.path.abspath(options.target_dir)

    if (not options.sort_key in SORT_KEYS):
        message = "options.sort_key:%s is not in set:%s" % (
            options.sort_key, SORT_KEYS)
        logging.error(message)
        print(message)
        sys.exit(1)

    message = get_volume_cold_ratio_rank(
        options.target_dir, tiering_policies, options.dir_levels, options.top_n, options.sort_key)
    print(message)
