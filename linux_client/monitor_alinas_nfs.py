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

VERSION = '1.4'

import subprocess
import argparse
import sys
import string
import httplib
import datetime
import time
import socket
import hashlib
import base64
import hmac
import json
import threading
import errno
import platform

CMS_DOMAIN_NAME = "metrichub-cms-cn-hangzhou.aliyuncs.com"
GENERAL_CONTACT = "NAS研发团队（钉钉群号：23110762）"
NAS_ALIYUN_SUFFIX = ".nas.aliyuncs.com"
MOUNT_FILENAME = "/proc/mounts"
DEBUG_MODE = False

def abort(e, msg="请处理以上问题，然后重新运行此脚本"):
    print >> sys.stderr, msg
    sys.exit(e)

def run_cmd(cmd):
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, shell=True)
    output, err = proc.communicate()
    return (proc.returncode, output)

def get_error_code(error_num):
    extended_errorcode = errno.errorcode
    extended_errorcode[123] = "ENOMEDIUM"
    extended_errorcode[124] = "EMEDIUMTYPE"
    if error_num in extended_errorcode:
        return extended_errorcode[error_num]
    return None

def get_ip_of_hostname(hostname):
    try:
        ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        abort(IOError, "%s地址解析失败" % hostname)
    return ip

def get_local_ip(domain_name, socket_num):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip = get_ip_of_hostname(domain_name)
    try:
        s.connect((ip, socket_num))
    except socket.error:
        abort(IOError, "%s:%d无法连通" % (domain_name, socket_num))
    return s.getsockname()[0]

KERNEL_VERS = platform.platform()
LOCAL_IP = get_local_ip(CMS_DOMAIN_NAME, 80)

class MountParser:
    @staticmethod
    def is_aliyun_nas_server(server):
        if server.endswith(NAS_ALIYUN_SUFFIX):
            return True
        return False

    @staticmethod
    def split_server_path(server_path_str):
        if ':' in server_path_str:
            server_path_list = server_path_str.split(':', 1)
            server = server_path_list[0]
            path = server_path_list[1] or '/'
        else:
            server = server_path_str
            path = '/'
        server_allowed = set(string.ascii_lowercase + \
                             string.ascii_uppercase + \
                             string.digits + '.' + '-')
        if not set(server) <= server_allowed \
           or not path.startswith('/'):
            return None
        server_path_dict = {}
        server_path_dict['server'] = server
        server_path_dict['path'] = path
        return server_path_dict

    @staticmethod
    def split_mount_status(mount_line):
        mount_status = mount_line.split()
        if len(mount_status) != 6:
            abort(OSError,
                  "%s的格式异常，请联系%s" % (
                      MOUNT_FILENAME, GENERAL_CONTACT))
        mount_status_dict = {}
        mount_status_dict['target'] = mount_status[0]
        mount_status_dict['mountpoint'] = mount_status[1]
        mount_status_dict['systype'] = mount_status[2]
        mount_status_dict['opt_str'] = mount_status[3]
        return mount_status_dict

    @staticmethod
    def read_mount_info():
        try:
            mount_file = open(MOUNT_FILENAME, 'r')
        except IOError as e:
            abort(e, "请注意此脚本只适用于Linux系统")

        mount_info_dict = {}
        mount_lines = mount_file.readlines()
        for mount_line in mount_lines:
            mount_status_dict = MountParser.split_mount_status(mount_line)
            target = mount_status_dict['target']
            mountpoint = mount_status_dict['mountpoint']
            systype = mount_status_dict['systype']
            opt_str = mount_status_dict['opt_str']
            if not systype.lower().startswith('nfs'):
                continue
            server_path_dict = MountParser.split_server_path(target)
            if not server_path_dict:
                continue
            server = server_path_dict['server']
            path = server_path_dict['path']
            if server not in mount_info_dict:
                mount_info_dict[server] = []
            mount_info_dict[server].append(
                (mountpoint, path, systype, opt_str))
        mount_file.close()
        return mount_info_dict


class CredentialsReader(object):
    def __init__(self, config_path):
        (self.accessid, self.accesskey) = self.load_config(config_path)

    def load_config(self, config_path):
        accessid = None
        accesskey = None
        try:
            config_file = open(config_path, 'r')
            for config_line in config_file.readlines():
                if "accessid" in config_line:
                    accessid = config_line.split('=')[1].strip()
                elif "accesskey" in config_line:
                    accesskey = config_line.split('=')[1].strip()
            config_file.close()
            if not accessid or not accesskey:
                raise ValueError
            else:
                return (accessid, accesskey)
        except Exception as e:
            abort(e, """
            请确认配置文件%s使用以下格式记录密钥信息：
            accessid = ACCESS_ID
            accesskey = ACCESS_KEY
            """ % config_path)

    def get_accessid(self):
        return self.accessid

    def get_accesskey(self):
        return self.accesskey


class CloudMonitorHandler(object):
    def __init__(self, accessid, accesskey,
                 event_name, event_content, group_id):
        self.method = "PUT"
        self.http_host = CMS_DOMAIN_NAME
        self.http_path = "/event/custom/upload"
        self.accessid = accessid
        self.accesskey = accesskey
        self.event_name = event_name
        self.event_content = event_content
        self.group_id = group_id

    def update_content(self, event_content):
        self.event_content = event_content

    def get_timestamp(self):
        now_local = datetime.datetime.fromtimestamp(time.time())
        timezone_seconds = time.timezone
        timestamp_str = "%s.%03d%+03d%02d" % (
            now_local.strftime("%Y%m%dT%H%M%S"),
            now_local.microsecond // 1000,
            -timezone_seconds // 3600,
            -timezone_seconds // 60 % 60
        )
        return timestamp_str

    def get_date(self):
        now_utc = datetime.datetime.utcfromtimestamp(time.time())
        weekday = ["Mon", "Tue", "Wed", "Thu",
                   "Fri", "Sat", "Sun"][now_utc.weekday()]
        month = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][now_utc.month - 1]
        date_str = "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
            weekday, now_utc.day, month, now_utc.year,
            now_utc.hour, now_utc.minute, now_utc.second
        )
        return date_str

    def get_body_dict(self):
        body_dict = {
            "content": self.event_content,
            "groupId": self.group_id,
            "name": self.event_name,
            "time": self.get_timestamp()
        }
        return body_dict

    def md5sum(self, body_str):
        md5sum = hashlib.md5()
        md5sum.update(body_str)
        return md5sum.hexdigest()

    def get_signstring(self, header_dict):
        cms_list = []
        for key in sorted(header_dict.keys()):
            if key.startswith('x-cms'):
                cms_list.append(
                    "%s:%s" % (key, header_dict[key])
                )
        sign_list = [
            self.method,
            header_dict['Content-MD5'],
            header_dict['Content-Type'],
            header_dict['Date'],
            '\n'.join(cms_list),
            self.http_path
        ]
        return '\n'.join(sign_list)

    def sign(self, signstring, accesskey):
        h = hmac.new(accesskey.encode(), signstring.encode(), hashlib.sha1)
        signature = base64.b16encode(h.digest()).strip()
        return signature

    def get_header_dict(self, body_str):
        header_dict = {}
        header_dict["User-Agent"] = "cms-python-openapi-v-1.0"
        header_dict["Content-MD5"] = self.md5sum(body_str)
        header_dict["Content-Type"] = "application/json"
        header_dict["Date"] = self.get_date()
        header_dict["x-cms-api-version"] = "1.0"
        header_dict["x-cms-ip"] = LOCAL_IP
        header_dict["x-cms-signature"] = "hmac-sha1"
        signstring = self.get_signstring(header_dict)
        signature = self.sign(signstring, self.accesskey)
        header_dict["Authorization"] = "%s:%s" % (self.accessid, signature)
        return header_dict

    def report_event(self):
        body_dict = self.get_body_dict()
        body_str = json.dumps([body_dict])
        header_dict = self.get_header_dict(body_str)
        conn = httplib.HTTPSConnection(self.http_host)
        conn.request(self.method, self.http_path, body_str, header_dict)
        res = conn.getresponse()
        print body_dict["time"], "Request:", body_str, "Response:", res.read()
        conn.close()


class CongestionChecker(object):
    def __init__(self, server, path, mountpoint,
                 cred_reader, group_id):
        self.mountpoint = mountpoint
        self.server = server
        self.path = path
        self.mountpoint = mountpoint
        self.cloud_monitor_handler = CloudMonitorHandler(
            cred_reader.get_accessid(),
            cred_reader.get_accesskey(),
            "NasCongestion",
            "",
            group_id
        )

    def run(self):
        (which_status, which_output) = run_cmd("which timeout")
        if which_status != 0:
            abort(e, "timeout工具缺失，请联系%s" % GENERAL_CONTACT)
        check_cmd = "stat -f %s" % self.mountpoint
        cmd = 'timeout 300s bash -c "%s"' % check_cmd
        (stat_status, stat_output) = run_cmd(cmd)
        if stat_status != 0 or DEBUG_MODE:
            self.report(stat_status)

    def report(self, stat_status):
        content = {
            'mount_target': "%s:%s" % (self.server, self.path),
            'kernel_version': KERNEL_VERS,
            'ecs_ip': LOCAL_IP,
            'local_dir': self.mountpoint,
            'error_type': get_error_code(stat_status)
        }
        self.cloud_monitor_handler.update_content(
            json.dumps([content])
        )
        self.cloud_monitor_handler.report_event()


class NasMonitor(object):
    def __init__(self):
        _parser = argparse.ArgumentParser(
            description='阿里云NAS (NFS) - Linux客户端监控')
        _parser.add_argument('group_id', type=str, default=None,
                             help="云监控应用分组的分组ID")
        _parser.add_argument("-D", "--debug", help="调试模式",
                             action="store_true")
        _parser.add_argument('-c', '--credentials_path', type=str,
                             required=False,
                             default="/etc/.cmscredentials",
                             help="密钥配置文件的路径")
        global DEBUG_MODE
        user_options = _parser.parse_args()
        group_id = user_options.group_id
        DEBUG_MODE = user_options.debug
        credentials_path = user_options.credentials_path

        self.check_list = []
        cred_reader = CredentialsReader(credentials_path)

        # mount_info_dict is a dict for /proc/mounts, with the key as
        # the server hostname, and the value as a list of (mountpoint,
        # path, systype, opt_str), with all tuple elements as strings
        mount_info_dict = MountParser.read_mount_info()

        for server, mount_tuple_list in mount_info_dict.items():
            if not MountParser.is_aliyun_nas_server(server):
                continue
            for mount_tuple in mount_tuple_list:
                (mountpoint, path, systype, opt_str) = mount_tuple
                self.check_list.append(
                    CongestionChecker(server, path, mountpoint,
                                      cred_reader, group_id))

    def run(self):
        threads = []
        for checker in self.check_list:
            t = threading.Thread(target=checker.run)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()


if __name__ == '__main__':
    monitor = NasMonitor()
    monitor.run()
