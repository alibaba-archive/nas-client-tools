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

import re
import os
import sys
import commands
import argparse
import socket
import time
import multiprocessing
import string
import platform
from abc import ABCMeta, abstractmethod

GENERAL_CONTACT = "NAS研发团队（钉钉群号：23110762）"
KERNEL_CONTACT = "NAS研发团队（钉钉群号：23177020）"
CONTAINER_CONTACT = "NAS研发团队（钉钉群号：21906225）"

SYSTEM_PORT_LIMIT = 1024
NFS_DEFAULT_PORT = 2049
NAS_ALIYUN_SUFFIX = ".nas.aliyuncs.com"
NAS_ALIYUN_EXTREME_SUFFIX = ".extreme" + NAS_ALIYUN_SUFFIX
MOUNT_FILENAME = "/proc/mounts"
NFS_SUPPORTED_VERS = {
    '3' : '/sbin/mount.nfs',
    '4.0' : '/sbin/mount.nfs4'
}
NFS_DEFAULT_VERS = '4.0'
NFS_DEFAULT_OPTS = {
    'rsize' : 1048576,
    'wsize' : 1048576,
    'timeo' : 600,
    'retrans' : 2,
    'noresvport' : None
}

NFS_V3_DEFAULT_OPTS = dict(NFS_DEFAULT_OPTS)
NFS_V3_DEFAULT_OPTS.update({
    'port' : NFS_DEFAULT_PORT,
    'mountport' : NFS_DEFAULT_PORT,
    'nolock' : None,
    'proto' : 'tcp'
})

HORIZONTAL_LINE = '-' * 50

VERBOSE = False

class colors:
    reset='\033[0m'
    bold='\033[01m'
    class fg:
        red='\033[31m'
        green='\033[32m'
        orange='\033[33m'
        blue='\033[34m'
        purple='\033[35m'
        cyan='\033[36m'
    class bg:
        red='\033[41m'

def colormsg(msg, color=colors.reset):
    return color + msg + colors.reset

def abort(e, msg="请处理以上问题，然后重新运行此脚本"):
    print >> sys.stderr, colors.fg.red + msg + colors.reset
    sys.exit(e)

def verbose_print(msg, newline=True):
    if VERBOSE:
        if newline:
            print(msg)
        else:
            print(msg),

def run_cmd(cmd):
    (status, output) = commands.getstatusoutput(cmd)
    if status != 0:
        verbose_print('')
        verbose_print(colormsg(output, colors.bold))
    return status == 0

def get_ip_of_hostname(hostname):
    try:
        ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        return None
    return ip

class MountParser:
    @staticmethod
    def is_aliyun_nas_server(server):
        if server.endswith(NAS_ALIYUN_EXTREME_SUFFIX):
            print(colormsg(
                "目前此脚本还不支持极速型NAS挂载排查，跳过自动检查",
                colors.fg.orange))
        elif server.endswith(NAS_ALIYUN_SUFFIX):
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
    def split_mount_options(options_str):
        options_dict = {}
        for option in options_str.split(','):
            if '=' in option:
                k, v = option.split('=', 1)
                options_dict[k] = v
            else:
                options_dict[option] = None
        return options_dict

    @staticmethod
    def join_mount_options(options_dict):
        options_list = []
        for k, v in options_dict.items():
            if v is None:
                options_list.append(str(k))
            else:
                options_list.append('%s=%s' % (str(k), str(v)))
        return ','.join(options_list)

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
    def recommend_mount_options(raw_opt_str):
        options = MountParser.split_mount_options(raw_opt_str)

        if 'nfsvers' in options:
            options['vers'] = options['nfsvers']
            del options['nfsvers']

        if 'vers' not in options or not options['vers']:
            options['vers'] = NFS_DEFAULT_VERS
        elif options['vers'] not in NFS_SUPPORTED_VERS:
            guess_vers = NFS_DEFAULT_VERS
            for vers in NFS_SUPPORTED_VERS:
                if vers[0] == str(options['vers'])[0]:
                    guess_vers = vers
            verbose_print(colormsg(
                "阿里云NAS不支持vers=%s，自动改成vers=%s挂载" % (
                    options['vers'], guess_vers),
                colors.fg.orange))
            options['vers'] = NFS_DEFAULT_VERS

        if 'soft' not in options and 'hard' not in options:
            options['hard'] = None

        if options['vers'] == '3':
            default_options = NFS_V3_DEFAULT_OPTS
        else:
            default_options = NFS_DEFAULT_OPTS

        for k, v in default_options.items():
            if k not in options:
                options[k] = str(v) if isinstance(v, (int, long)) else v

        return MountParser.join_mount_options(options)

    @staticmethod
    def normalize_mount_options(rcmd_opt_str):
        options = MountParser.split_mount_options(rcmd_opt_str)

        # Fix compatibility issues
        if '.' in options['vers']:
            major, minor = options['vers'].split('.', 1)
            options['vers'] = major
            options['minorversion'] = minor

        return MountParser.join_mount_options(options)

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

    @staticmethod
    def get_mount_cmd(raw_opt_str, mount_addr, export_path, local_dir):
        rcmd_opt_str = MountParser.recommend_mount_options(raw_opt_str)
        opt_dict = MountParser.split_mount_options(rcmd_opt_str)
        if not opt_dict or 'vers' not in opt_dict:
            return None
        vers = opt_dict['vers']
        if vers not in NFS_SUPPORTED_VERS:
            return None
        binary = "sudo mount -t nfs"
        nmlz_opt_str = MountParser.normalize_mount_options(rcmd_opt_str)
        mount_cmd = "%s -o %s %s:%s %s" % (
            binary, nmlz_opt_str, mount_addr, export_path, local_dir)
        return mount_cmd

    @staticmethod
    def check_sys_port_occupied(ss_output):
        tcp_conn_list = ss_output.split('\n')
        no_sys_port_occupied = True
        occupied_sys_port_list = []
        for tcp_conn_line in tcp_conn_list:
            tcp_conn = tcp_conn_line.split()
            if len(tcp_conn) != 5 \
               or ':' not in tcp_conn[3]:
                continue
            local_port = int(tcp_conn[3].split(':', 1)[1])
            if local_port < SYSTEM_PORT_LIMIT:
                occupied_sys_port_list.append(str(local_port))
                no_sys_port_occupied = False
        if not no_sys_port_occupied:
            verbose_print('')
            verbose_print(colormsg(
                "现存NFS连接占用了以下系统端口：" + \
                ','.join(occupied_sys_port_list),
                colors.fg.orange))
        return no_sys_port_occupied

    @staticmethod
    def parse_fuser_output(local_dir):
        if not run_cmd("which fuser"):
            abort(OSError,
                  """
                  fuser工具不存在，请选择以下命令安装
                  CentOS/RedHat：yum install -y psmisc
                  Debian/Ubuntu：apt-get --yes install psmisc
                  安装后再次运行脚本，如果仍然失败，请联系%s
                  """ % GENERAL_CONTACT)
        (status, output) = commands.getstatusoutput(
            "fuser -mv %s" % local_dir)
        if status != 0:
            # Some kernels return error code when nothing is found
            return {}
        fuser_list = output.split('\n')
        fuser_dict = {}
        for fuser_line in fuser_list:
            fuser_line_list = fuser_line.split()
            if len(fuser_line_list) == 5:
                (user, pid, access, command) = fuser_line_list[1:]
            elif len(fuser_line_list) != 4:
                continue
            else:
                (user, pid, access, command) = fuser_line_list
            if pid.lower() == "pid":
                # skip the title line
                continue
            if access.lower() == "mount":
                # skip all mount commands
                continue
            fuser_dict[pid] = (user, access, command)
        return fuser_dict

    @staticmethod
    def get_fuser_list(local_dir):
        fuser_str_list = []
        fuser_dict = MountParser.parse_fuser_output(local_dir)
        if fuser_dict:
            fuser_str_list.append(
                "%s  %s  %s" % ("PID", "USER", "COMMAND"))
        for pid, pid_tuple in fuser_dict.items():
            (user, access, command) = pid_tuple
            fuser_str_list.append(
                "%s  %s  %s" % (pid, user, command))
        return fuser_str_list


class ConditionChecker(object):
    __metaclass__ = ABCMeta
    PASS_COLOR = colors.fg.green
    FAIL_COLOR = colors.fg.red
    EXIT_ON_FAIL = True
    CHECK_MSG = ""
    REPAIR_MSG = ""
    FAIL_MSG = "解决以上问题之后，请重新运行此脚本继续排查"

    def check(self):
        return False

    def prompt(self):
        return True

    def repair(self):
        verbose_print('')
        return False

    def alarm_upgrade_kernel(self, kernel_version):
        print(colormsg(
            """
            内核版本%s存在已知缺陷，请联系%s
            详细信息请参考https://help.aliyun.com/document_detail/114129.html
            """ % (
                kernel_version,
                KERNEL_CONTACT),
            colors.fg.blue))

    def alarm_unmount_server(self, mount_info_dict, mount_addr):
        if mount_addr not in mount_info_dict \
           or not mount_info_dict[mount_addr]:
            print(colormsg(
                "还有shell没退出曾经挂载过NFS文件系统的目录，如无法找到请重启机器后再挂载",
                colors.fg.blue))
            return
        mount_tuple_list = mount_info_dict[mount_addr]
        fuser_str_list = []
        mountpoint_list = []
        mount_cmd_list = []
        for mount_tuple in mount_tuple_list:
            (mountpoint, path, systype, opt_str) = mount_tuple
            fuser_str_list.extend(
                MountParser.get_fuser_list(mountpoint))
            mountpoint_list.append(mountpoint)
            mount_cmd_list.append(
                MountParser.get_mount_cmd(
                    opt_str, mount_addr, path, mountpoint))
        delimiter = '\n' + ' ' * 24
        warning_msg = colormsg(
            """
            以下操作建议在业务低峰期进行
            """, colors.fg.orange) + colormsg(
            """
            建议将以下步骤复制保存后再执行操作
            请卸载所有使用挂载点%s的本地目录，再重新挂载：
                1. 停止以下所有对挂载路径进行操作的应用（如果没有显示请跳过），kill前请根据实际业务情况评估影响
                        %s
                2. 卸载所有相关本地挂载路径，如果返回“device is busy”，请确认上一步的所有进程已经被kill
                        sudo umount %s
                3. 确认所有相关本地挂载路径完成卸载，以下命令应该返回为空
                        mount | grep %s
                4. 执行以下命令，重新挂载以上所有目录（挂载命令已经加入noresvport）
                        %s
            如果重新挂载出现相同问题，可能是遇到了客户端Linux的缺陷，请择机重启机器后再挂载
            """ % (
                mount_addr,
                delimiter.join(fuser_str_list),
                ' '.join(mountpoint_list),
                mount_addr,
                delimiter.join(mount_cmd_list)),
            colors.fg.blue)
        print(warning_msg)

    def run(self):
        try:
            verbose_print(HORIZONTAL_LINE)
            if self.CHECK_MSG:
                verbose_print(self.CHECK_MSG, newline=False)
                sys.stdout.flush()
            check_passed = self.check()
            if not check_passed:
                prompt_passed = self.prompt()
                if prompt_passed:
                    if self.REPAIR_MSG:
                        verbose_print(self.REPAIR_MSG, newline=False)
                        sys.stdout.flush()
                    repair_passed = self.repair()
                    if repair_passed:
                        verbose_print(colormsg(
                            "通过", self.PASS_COLOR))
                        return repair_passed
                    else:
                        if self.FAIL_MSG:
                            verbose_print(colormsg(
                                self.FAIL_MSG, self.FAIL_COLOR))
                        if self.EXIT_ON_FAIL:
                            sys.exit(1)
                        return repair_passed
                else:
                    print(colormsg(
                        "用户选择结束脚本，请手动解决上述问题后，再次运行此脚本继续排查其他问题",
                        self.FAIL_COLOR))
                    if self.EXIT_ON_FAIL:
                        sys.exit(1)
                    return prompt_passed
            else:
                verbose_print(colormsg("通过", self.PASS_COLOR))
                return check_passed
        except Exception as e:
            abort(e)


class RootUserChecker(ConditionChecker):
    CHECK_MSG = "正在检查root操作权限..."
    REPAIR_MSG = "请使用sudo再次运行此脚本"

    def check(self):
        if os.geteuid() != 0:
            verbose_print('')
            print(colormsg(
                """
                此脚本需要使用root权限执行
                """,
                colors.fg.blue))
        return os.geteuid() == 0


class KernelVersChecker(ConditionChecker):
    CHECK_MSG = "正在检查系统内核版本..."
    REPAIR_MSG = "当前内核版本存在已知问题"

    def check(self):
        sysname = platform.system()
        version = platform.release()
        self.kernel_version = version

        # Only Linux is supported
        if sysname != "Linux":
            abort(OSError, "阿里云NAS的NFS文件系统目前只支持Linux和Windows挂载，不支持macOS或类似系统挂载")

        # Parse kernel version into major and minor by '-'
        if '-' in version:
            (major, minor) = version.split('-', 1)
        else:
            major = version
            minor = '0'

        # Check if the kernel version is known to have problems
        bad_kernels = {
            '4.2.0': ('18', '19'),
            '3.10.0' : ('', '229.11.1'),
            '2.6.32' : ('696', '696.10.1')
        }
        if major in bad_kernels \
           and minor >= bad_kernels[major][0] \
           and minor < bad_kernels[major][1]:
            verbose_print('')
            return False
        return True

    def repair(self):
        verbose_print('')
        self.alarm_upgrade_kernel(self.kernel_version)
        return False


class StatChecker(ConditionChecker):
    EXIT_ON_FAIL = False
    CHECK_MSG = "正在检查挂载的NFS文件系统能否联通..."
    REPAIR_MSG = "挂载的NFS文件系统无法联通"
    FAIL_MSG = ""

    def __init__(self, local_dir):
        self.local_dir = local_dir

    def check(self):
        cmd = "stat %s" % self.local_dir
        if run_cmd("which timeout"):
            cmd = 'timeout 2s bash -c "%s"' % cmd
        return run_cmd(cmd)


class MountOptionChecker(ConditionChecker):
    EXIT_ON_FAIL = False
    CHECK_MSG = "正在检查挂载选项是否包含noresvport..."
    REPAIR_MSG = "挂载选项没有包含noresvport"
    FAIL_MSG = ""

    def __init__(self, opt_str):
        self.opt_str = opt_str

    def check(self):
        contained = ("noresvport" in self.opt_str)
        if not contained:
            verbose_print('')
        return contained


class PortRangeChecker(ConditionChecker):
    EXIT_ON_FAIL = False
    CHECK_MSG = "正在检查NFS连接是否使用了noresvport参数..."
    REPAIR_MSG = "现存NFS连接没有使用noresvport参数"
    FAIL_MSG = ""

    def __init__(self, mount_info_dict,
                 mount_addr):
        self.mount_info_dict = mount_info_dict
        self.mount_addr = mount_addr

    def check(self):
        if not run_cmd("which ss"):
            abort(OSError, "ss工具不存在，请联系%s" % GENERAL_CONTACT)
        ip = get_ip_of_hostname(self.mount_addr)
        if ip is None:
            # Found no valid IP address for mount_addr
            return True

        remote_ip_port = str(ip) + ':' + str(NFS_DEFAULT_PORT)

        (status, output) = commands.getstatusoutput(
            "ss -nt | grep ESTAB | grep " + remote_ip_port)
        if status != 0:
            # Found no existing TCP connection for mount_addr
            return True
        return MountParser.check_sys_port_occupied(output)


class EffNoresvportChecker(ConditionChecker):
    EXIT_ON_FAIL = False
    CHECK_MSG = "正在综合检查挂载点的noresvport是否生效...\n"
    REPAIR_MSG = "挂载点没有使用noresvport参数"
    FAIL_MSG = ""

    def __init__(self, mount_info_dict,
                 mount_addr, need_repair):
        self.mount_info_dict = mount_info_dict
        self.mount_addr = mount_addr
        self.need_repair = need_repair
        self.mount_tuple_list = None
        if self.mount_addr in mount_info_dict:
            self.mount_tuple_list = mount_info_dict[self.mount_addr]

    def check(self):
        if not self.mount_tuple_list:
            # Ignore the mount address if it has not been mounted
            return True

        ip = get_ip_of_hostname(self.mount_addr)

        if ip is None:
            if self.mount_addr not in self.mount_info_dict:
                abort(ValueError, "挂载点%s无法在%s中找到，请联系%s" % (
                    self.mount_addr, MOUNT_FILENAME, GENERAL_CONTACT))
            mount_tuple_list = self.mount_info_dict[self.mount_addr]
            mountpoint_list = []
            for mount_tuple in mount_tuple_list:
                mountpoint_list.append(mount_tuple[0])
            print(colormsg(
                "挂载点%s疑似已被删除，请登录NAS控制台确认已删除，然后在业务低峰期转移相关任务，并且卸载本地目录：umount -l %s" % (
                    self.mount_addr, ' '.join(mountpoint_list)),
                colors.fg.red))
            return False

        noresvport_effective = True
        for mount_tuple in self.mount_tuple_list:
            (mountpoint, path, systype, opt_str) = mount_tuple
            StatChecker(mountpoint).run()
            noresvport_effective &= MountOptionChecker(opt_str).run()

        noresvport_effective &= PortRangeChecker(
            self.mount_info_dict, self.mount_addr).run()

        if not noresvport_effective:
            print(colormsg(
                "挂载点地址%s需要使用noresvport重新挂载" % self.mount_addr,
                colors.fg.red))

        return noresvport_effective

    def repair(self):
        verbose_print('')
        if self.need_repair:
            self.alarm_unmount_server(
                self.mount_info_dict, self.mount_addr)
        return False


class BadConnChecker(ConditionChecker):
    EXIT_ON_FAIL = False
    CHECK_MSG = "正在检查是否存在残留的坏连接"
    REPAIR_MSG = "存在需要重启修复的残留连接"
    FAIL_MSG = ""

    def __init__(self, mount_info_dict, need_repair):
        self.mount_info_dict = mount_info_dict
        self.need_repair = need_repair

    def check(self):
        ip_list = []
        for server in self.mount_info_dict:
            ip = get_ip_of_hostname(server)
            if ip is not None:
                ip_list.append(ip)
        ip_list_str = '|'.join(ip_list)
        cmd = 'ss -nt | grep ESTAB | grep -w %s' % str(NFS_DEFAULT_PORT)
        if ip_list_str:
            cmd += ' | grep -Ev "%s"' % ip_list_str
        (status, output) = commands.getstatusoutput(cmd)
        if status != 0 or not output:
            # Found no leaked TCP connection
            return True
        no_sys_port_occupied = MountParser.check_sys_port_occupied(output)
        if not no_sys_port_occupied:
            print(colormsg(
                "存在没有使用noresvport的残留NFS连接，请在业务低峰期重启ECS修复",
                colors.fg.red))
        return no_sys_port_occupied

    def repair(self):
        verbose_print('')
        if self.need_repair:
            print(colormsg(
            """
            存在残留的NFS连接没有使用noresvport，为了避免后续的挂载复用此连接，请在业务低峰期重启ECS，回收此连接
            """,
                colors.fg.blue))
        return False


class NfsMountHelper(object):
    def __init__(self):
        args_dict = self.parse_args()
        self.need_repair = args_dict['need_repair']
        self.check_list = self.prepare(args_dict)

    def parse_args(self):
        global VERBOSE
        _parser = argparse.ArgumentParser(description='阿里云NAS (NFS) - Linux客户端检查')
        _parser.add_argument("-v", "--verbose", help="显示所有执行的检查项目",
                             action="store_true")
        _parser.add_argument("-r", "--repair", help="显示ECS的修复方案",
                             action="store_true")
        user_options = _parser.parse_args()
        args_dict = {}
        VERBOSE = user_options.verbose
        args_dict['need_repair'] = user_options.repair
        return args_dict

    def prepare(self, args_dict):
        check_list = [
            RootUserChecker(),
            KernelVersChecker(),
        ]

        # mount_info_dict is a dict for /proc/mounts, with the key as
        # the server hostname, and the value as a list of (mountpoint,
        # path, systype, opt_str), with all tuple elements as strings
        mount_info_dict = MountParser.read_mount_info()

        for server, mount_tuple_list in mount_info_dict.items():
            if not MountParser.is_aliyun_nas_server(server):
                continue
            check_list.append(
                EffNoresvportChecker(
                    mount_info_dict, server, self.need_repair))

        check_list.append(
            BadConnChecker(mount_info_dict, self.need_repair))

        return check_list

    def run(self):
        all_good = True
        for checker in self.check_list:
            all_good &= checker.run()
        if all_good:
            print(colormsg(
                "本台ECS无须处理noresvport问题",
                colors.fg.green))
        else:
            if not self.need_repair:
                print(colormsg(
                    "如果您正使用ECS直接挂载NAS，请使用-r参数重新执行此脚本，查看详细解决方案",
                    colors.fg.orange))
            print(colormsg(
                "如果您正使用容器挂载NAS，请参考文档 https://yq.aliyun.com/articles/707169 处理，如有疑问请联系%s" % CONTAINER_CONTACT,
                colors.fg.orange))
            print(colormsg(
                "请处理本台ECS的noresvport问题，完毕之后请再次运行此脚本，确认风险排除",
                colors.fg.orange))


if __name__ == '__main__':
    verbose_print("=== 阿里云NAS (NFS) - Linux可用性风险排查开始 ===")
    helper = NfsMountHelper()
    helper.run()
    verbose_print("=== 阿里云NAS (NFS) - Linux可用性风险排查结束 ===")
