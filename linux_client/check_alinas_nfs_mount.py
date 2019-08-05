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

VERBOSE = True

PACKAGE_MANAGER = None
class PacMan:
    name = None
    cmd_install = None
    cmd_query = None
    cmd_update = None
    cmd_test = None
    pkg_nfs = None

class Yum(PacMan):
    name = "yum"
    cmd_install = "yum install -y"
    cmd_query = "rpm -q"
    cmd_update = None
    cmd_test = "yum list kernel"
    pkg_nfs = "nfs-utils"

class AptGet(PacMan):
    name = "apt-get"
    cmd_install = "apt-get install -y"
    cmd_query = "dpkg -l | grep -E '^ii' | grep"
    cmd_update = "apt-get update"
    cmd_test = "apt-get check"
    pkg_nfs = "nfs-common"

# TODO - add zypper and pkg

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

def print_cmd(cmd):
    print(colormsg(
        """
        %s
        """ % cmd, colors.fg.blue))

class questions:
    mount_addr_exist = {
        'question' : "挂载点地址是否输入正确，而且未被删除？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            请找到并使用有效的挂载点地址：
                1. 登录NAS控制台
                2. 点击左侧栏目中的“文件系统列表”
                3. 点击NAS实例名，进入“文件系统详情”页面
                4. 复制挂载地址，重新调用脚本时粘贴使用
            """,
            colors.fg.blue),
        'title' : ""
    }

    using_ecs = {
        'question' : "当前机器是不是阿里云ECS实例？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            强烈建议使用阿里云ECS挂载NAS享受最佳性能体验
            """,
            colors.fg.blue),
        'title' : ""
    }

    idc_connected = {
        'question' : "当前机器所在的本地IDC是否已经打通访问NAS的特殊方式？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            本地IDC挂载NAS需要使用NAT、VPN或者SFTP，请参考以下文档
            NAT:  https://help.aliyun.com/document_detail/57628.html
            VPN:  https://help.aliyun.com/document_detail/54998.html
            SFTP: https://help.aliyun.com/document_detail/101120.html
            """,
            colors.fg.blue),
        'title' : ""
    }

    same_uid = {
        'question' : "当前ECS与NAS是否属于同一个UID？或者是否已经打通跨账号VPC专线？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            跨账号挂载NAS，请参考以下文档打通VPC专线
            https://help.aliyun.com/document_detail/108679.html
            """,
            colors.fg.blue),
        'title' : ""
    }

    same_region = {
        'question' : "当前ECS与NAS是否属于同一地域（例如杭州）？或者是否已经打通跨地域VPC专线？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            强烈建议使用同地域（最好同可用区）的阿里云ECS挂载NAS享受最佳性能体验
            跨地域挂载NAS，请参考以下文档打通VPC专线
            https://help.aliyun.com/document_detail/54998.html?#h2-url-4
            """,
            colors.fg.blue),
        'title' : ""
    }

    using_vpc = {
        'question' : "提供的NAS挂载点是否属于VPC类型？",
        'yes_response' : "",
        'no_response' : "",
        'title' : ""
    }

    connected_vpc = {
        'question' : "当前机器和NAS挂载点是否在同一个VPC里？或者是否已经打通VPC专线？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            一、跨账号、跨地域或者本地IDC打通VPC专线的方法，请重新运行此脚本，准确回答相应问题解决
            二、相同账号、相同地域的不同VPC，请参考以下文档打通专线访问
                https://help.aliyun.com/document_detail/108665.html
            三、如果是挂载点的VPC配置错误，请按以下步骤修改
                1. 登录NAS控制台
                2. 点击左侧栏目中的“权限组”
                3. 点击“管理规则”，找到或者创建一个向ECS所在网段开放的专有网络权限组（一般使用“VPC默认权限组（全部允许）”即可）
                4. 点击左侧栏目中的“文件系统列表”
                5. 点击NAS实例名，进入“文件系统详情”页面
                6. 删除处于错误VPC内的挂载点
                7. 点击“添加挂载点”
                    a. 在“VPC网络”下拉列表中选择ECS所在的VPC
                    b. 在“交换机”下拉列表选择任意交换机
                    c. 在“权限组”下拉列表选择第3步获得的权限组，点击“确定”即可
            """,
            colors.fg.blue),
        'title' : ""
    }

    classic_configured = {
        'question' : "当前机器的阿里云内网IP是否在挂载点的（经典网络类型）权限组内？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            经典网络权限组配置错误，请按以下步骤修改：
                1. 登录NAS控制台
                2. 点击左侧栏目中的“权限组”
                3. 点击“管理规则”，找到或者创建一个向ECS内网IP开放的经典网络权限组
                4. 点击左侧栏目中的“文件系统列表”
                5. 点击NAS实例名，进入“文件系统详情”页面
                6. 在挂载点一行点击“修改权限组”
                7. 在“修改为”下拉列表中选择第3步获得的权限组，点击“确定”即可
            """,
            colors.fg.blue),
        'title' : ""
    }

    vpc_configured = {
        'question' : "当前机器的阿里云内网IP是否在挂载点的（专有网络类型）权限组内？",
        'yes_response' : "",
        'no_response' : colormsg(
            """
            专有网络权限组配置错误，请按以下步骤修改：
                1. 登录NAS控制台
                2. 点击左侧栏目中的“权限组”
                3. 点击“管理规则”，找到或者创建一个向ECS内网IP开放的专有网络权限组
                4. 点击左侧栏目中的“文件系统列表”
                5. 点击NAS实例名，进入“文件系统详情”页面
                6. 在挂载点一行点击“修改权限组”
                7. 在“修改为”下拉列表中选择第3步获得的权限组，点击“确定”即可
            """,
            colors.fg.blue),
        'title' : ""
    }

    out_of_fund = {
        'question' : "NAS所属的阿里云账号是否已经欠费？",
        'yes_response' : colormsg(
            """
            请登录阿里云控制台，点击顶部栏“费用”按钮，再点击“充值”，结束欠费状态
            """,
            colors.fg.blue),
        'no_response' : "",
        'title' : ""
    }

    smb_filesystem = {
        'question' : "NAS文件系统是否属于SMB协议类型？",
        'yes_response' : colormsg(
            """
            一、如果需要挂载SMB类型的NAS文件系统，请参考以下文档，此脚本不适用于SMB文件系统
                Windows（推荐）: https://help.aliyun.com/document_detail/90535.html
                Linux（不推荐）: https://help.aliyun.com/knowledge_detail/110839.html?#h2-url-2
            二、如果购买了错误类型的文件系统，请按以下步骤操作
                1. 登录NAS控制台，进入“文件系统列表”，点击“创建文件系统”，注意“协议类型”一项选择“NFS”
                2. """, colors.fg.blue)
        + colormsg("反复确认SMB文件系统完全没有数据（文件系统删除后无法恢复）", colors.bg.red)
        + colormsg("""，再删除购买错误的文件系统
            """,
            colors.fg.blue),
        'no_response' : "",
        'title' : ""
    }

    mount_addr_banned = {
        'question' : "当前挂载点是否在NAS控制台上被禁用？",
        'yes_response' : colormsg(
            """
            挂载点被禁用，请按以下步骤修改：
                1. 登录NAS控制台
                2. 点击左侧栏目中的“文件系统列表”
                3. 点击NAS实例名，进入“文件系统详情”页面
                4. 在相应挂载点一行点击“激活”，确定即可
            """,
            colors.fg.blue),
        'no_response' : "",
        'title' : ""
    }

    answer_acurate = {
        'question' : "您确定以上回答都准确无误吗？请登录阿里云控制台，仔细确认所有信息之后回答",
        'yes_response' : colormsg(
            """
            遇到非典型情况，请将脚本的全部输出截屏，并联系%s
            """ % GENERAL_CONTACT,
            colors.fg.blue),
        'no_response' : "",
        'title' : ""
    }


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

    def ask_user(self, question, yes_response="", no_response="",
                 title=colormsg(
                     "请输入'Yes'继续执行脚本，或者'No'结束脚本",
                     colors.bold)):
        yes = set(['yes','ye', 'y'])
        no = set(['no','n'])
        while True:
            if title:
                print(title)
            answer = raw_input(
                colormsg(question, colors.fg.cyan) + " [Yes/No]: ").lower()
            if answer in yes:
                if yes_response:
                    print(yes_response)
                return True
            elif answer in no:
                if no_response:
                    print(no_response)
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
            如果重新挂载出现相同问题，可能是遇到了客户端Linux的漏洞，请择机重启机器后再挂载
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
        return os.geteuid() == 0


class MountStatusChecker(ConditionChecker):
    CHECK_MSG = "正在检查本地路径是否已经挂载..."
    REPAIR_MSG = "本地路径已经挂载了目标"

    def __init__(self, mount_info_dict, mount_addr,
                 export_path, local_dir):
        self.mount_info_dict = mount_info_dict
        self.mount_addr = mount_addr
        self.export_path = export_path
        self.local_dir = local_dir
        self.mount_target_match = False
        self.mount_target_path = None

    def check(self):
        for server, mount_tuple_list in self.mount_info_dict.items():
            for mount_tuple in mount_tuple_list:
                (mountpoint, path, systype, opt_str) = mount_tuple
                if mountpoint == self.local_dir:
                    if server == self.mount_addr \
                       and path == self.export_path:
                        self.mount_target_match = True
                    self.mount_target_path = "%s:%s" % (server, path)
                    verbose_print('')
                    return False
        return True

    def repair(self):
        verbose_print('')
        if self.mount_target_match:
            print(colormsg(
            """
            本地路径%s已经挂载了目标%s，请执行以下脚本检查挂载参数
            wget https://raw.githubusercontent.com/alibabacloudnas/nas-client-tools/master/check_noresvport.py -P /tmp/
            python /tmp/check_noresvport.py
            """ % (self.local_dir, self.mount_target_path),
                colors.fg.blue))
        else:
            print(colormsg(
            """
            本地路径%s已经挂载了目标%s，请指定其他本地路径挂载
            """ % (self.local_dir, self.mount_target_path),
                colors.fg.blue))
        return False


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

        # Get the package manager
        global PACKAGE_MANAGER
        (status, output) = commands.getstatusoutput("which yum")
        if status == 0:
            PACKAGE_MANAGER = Yum
        (status, output) = commands.getstatusoutput("which apt-get")
        if status == 0:
            PACKAGE_MANAGER = AptGet
        if not PACKAGE_MANAGER:
            verbose_print('')
            abort(OSError, "此脚本只支持yum和apt-get包管理器")

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


class PacManChecker(ConditionChecker):
    CHECK_MSG = "正在检查包管理器能否访问网络..."
    REPAIR_MSG = "包管理器网络异常，请检查网络配置"

    def check(self):
        cmd = PACKAGE_MANAGER.cmd_test
        if run_cmd("which timeout"):
            cmd = 'timeout 10s bash -c "%s"' % cmd
        return run_cmd(cmd)


class NfsClientChecker(ConditionChecker):
    CHECK_MSG = "正在检查NFS客户端是否已经安装..."
    REPAIR_MSG = "需要安装NFS客户端"

    def check(self):
        return run_cmd("%s %s" % (
            PACKAGE_MANAGER.cmd_query, PACKAGE_MANAGER.pkg_nfs))

    def repair(self):
        verbose_print('')
        print("请执行以下命令安装NFS客户端")
        cmd = ''
        if PACKAGE_MANAGER == AptGet:
            cmd += "%s && " % AptGet.cmd_update
        cmd += "%s %s" % (
            PACKAGE_MANAGER.cmd_install, PACKAGE_MANAGER.pkg_nfs)
        print_cmd(cmd)
        return False


class PingChecker(ConditionChecker):
    CHECK_MSG = "正在ping挂载点，确认网络畅通..."
    REPAIR_MSG = "ping挂载点失败，请回答以下问题排查网络情况"

    def __init__(self, mountaddress):
        self.mountaddress = mountaddress

    def check(self):
        return run_cmd("ping -c 2 -W 1 " + self.mountaddress)

    class network_states:
        init = 1
        valid = 2
        unexpected = 3

    def repair(self):
        verbose_print('')
        state = self.network_states.init
        while True:
            if state == self.network_states.init:
                if not self.ask_user(**questions.mount_addr_exist):
                    break;
                elif self.ask_user(**questions.using_ecs):
                    if self.ask_user(**questions.same_uid) \
                       and self.ask_user(**questions.same_region):
                        state = self.network_states.valid
                    else:
                        break;
                elif self.ask_user(**questions.idc_connected):
                    state = self.network_states.valid
                else:
                    break;
            elif state == self.network_states.valid:
                if self.ask_user(**questions.using_vpc):
                    if self.ask_user(**questions.connected_vpc):
                        state = self.network_states.unexpected
                    else:
                        break;
                elif self.ask_user(**questions.classic_configured):
                    state = self.network_states.unexpected
                else:
                    break;
            elif state == self.network_states.unexpected:
                if not self.ask_user(**questions.answer_acurate):
                    state = self.network_states.init
                else:
                    break;
            else:
                abort(ValueError, "Unexpected network state");
        return False


class TelnetAppChecker(ConditionChecker):
    CHECK_MSG = "正在检查telnet是否已经安装..."
    REPAIR_MSG = "需要安装telnet工具"
    PKG_NAME = "telnet"

    def check(self):
        return run_cmd("%s %s" % (
            PACKAGE_MANAGER.cmd_query, self.PKG_NAME))

    def repair(self):
        verbose_print('')
        print("请执行以下命令安装telnet工具")
        print_cmd("%s %s" % (
            PACKAGE_MANAGER.cmd_install, self.PKG_NAME))
        return False


class TimeoutChecker(ConditionChecker):
    CHECK_MSG = "正在telnet挂载点，确认ECS安全组..."
    REPAIR_MSG = "telnet命令超时，请检查ECS安全组配置"

    def __init__(self, mountaddress):
        self.mountaddress = mountaddress

    def check(self):
        cmd = "(sleep 2; echo -e '\x1dclose\x0d') | telnet %s %s" % (
            self.mountaddress, str(NFS_DEFAULT_PORT))
        p = multiprocessing.Process(target=run_cmd, args=(cmd,))
        p.start()
        p.join(5)
        if p.is_alive():
            p.terminate()
            p.join()
            verbose_print('')
            return False
        return True

    def repair(self):
        ip = socket.gethostbyname(self.mountaddress)
        print(colormsg(
            """
            请修改本台ECS的安全组配置，允许访问挂载点IP
                1. 登录ECS控制台
                2. 点击ECS实例名进入实例详情页面
                3. 点击左侧栏目中的“本实例安全组”
                4. 点击“配置规则”
                5. 在“入方向”和“出方向”页面中找到所有授权策略为“拒绝”的规则
                6. 查看拒绝规则的“授权对象”网段中是否包含挂载点IP：%s
                7. 将挂载点IP从相关的拒绝规则中剔除
            """ % ip,
            colors.fg.blue))
        return False


class TelnetChecker(ConditionChecker):
    CHECK_MSG = "正在telnet挂载点，确认挂载权限..."
    REPAIR_MSG = "telnet挂载点失败，请回答以下问题排查挂载权限"

    def __init__(self, mountaddress):
        self.mountaddress = mountaddress

    def check(self):
        return run_cmd("(sleep 2; echo -e '\x1dclose\x0d') | telnet %s %s" %
                       (self.mountaddress, str(NFS_DEFAULT_PORT)))

    class auth_states:
        init = 1
        valid = 2
        unexpected = 3

    def repair(self):
        verbose_print('')
        state = self.auth_states.init
        while True:
            if state == self.auth_states.init:
                if self.ask_user(**questions.out_of_fund):
                    break;
                elif self.ask_user(**questions.smb_filesystem):
                    break;
                elif self.ask_user(**questions.mount_addr_banned):
                    break;
                else:
                    state = self.auth_states.valid
            elif state == self.auth_states.valid:
                if self.ask_user(**questions.using_vpc):
                    if self.ask_user(**questions.vpc_configured):
                        state = self.auth_states.unexpected
                    else:
                        break;
                elif self.ask_user(**questions.classic_configured):
                    state = self.auth_states.unexpected
                else:
                    break;
            elif state == self.auth_states.unexpected:
                if not self.ask_user(**questions.answer_acurate):
                    state = self.auth_states.init
                else:
                    break;
            else:
                abort(ValueError, "Unexpected auth state");
        return False


class PortRangeChecker(ConditionChecker):
    CHECK_MSG = "正在检查NFS连接是否使用了noresvport参数..."
    REPAIR_MSG = "现存NFS连接没有使用noresvport参数"

    def __init__(self, mount_info_dict,
                 mount_addr):
        self.mount_info_dict = mount_info_dict
        self.mount_addr = mount_addr

    def check(self):
        if not run_cmd("which ss"):
            abort(OSError, "ss工具不存在，请联系%s" % GENERAL_CONTACT)
        ip = socket.gethostbyname(self.mount_addr)
        remote_ip_port = str(ip) + ':' + str(NFS_DEFAULT_PORT)

        (status, output) = commands.getstatusoutput(
            "ss -nt | grep " + remote_ip_port)
        if status != 0:
            # Found no existing TCP connection for mount_addr
            return True
        return MountParser.check_sys_port_occupied(output)

    def repair(self):
        verbose_print('')
        self.alarm_unmount_server(
            self.mount_info_dict, self.mount_addr)
        return False


class DirExistenceChecker(ConditionChecker):
    CHECK_MSG = "正在检查本地目录是否存在..."
    REPAIR_MSG = "需要创建本地目录"

    def __init__(self, local_dir):
        self.local_dir = local_dir

    def check(self):
        return run_cmd('[ -d "%s" ]' % self.local_dir)

    def repair(self):
        verbose_print('')
        print("请执行以下命令创建本地目录")
        print_cmd("mkdir -p %s" % self.local_dir)
        return False


class DirEmptyChecker(ConditionChecker):
    CHECK_MSG = "正在检查本地目录是否为空..."
    REPAIR_MSG = "指定目录不是空目录"

    def __init__(self, local_dir):
        self.local_dir = local_dir

    def check(self):
        return run_cmd('[ -z "$(ls -A %s)" ]' % self.local_dir)

    def repair(self):
        verbose_print('')
        print(colormsg(
            """
            本地目录%s不是空目录，挂载后将无法找到此目录中的文件
            建议将现有目录移动到其他位置，或者使用其他本地目录挂载
            """ % self.local_dir,
            colors.fg.blue))
        return False


class KernelParamChecker(ConditionChecker):
    FAIL_COLOR = colors.fg.orange
    EXIT_ON_FAIL = False
    REPAIR_MSG = colormsg(
        "建议以root身份手动执行以下命令修改内核参数，优化NAS性能",
        colors.bold)
    FAIL_MSG = "略过"

    def __init__(self, fullname, value, pass_op):
        if '.' not in fullname:
            abort(ValueError, "invalid kernel parameter")
        (self.module, self.param) = fullname.rsplit('.', 1)
        self.CHECK_MSG = "正在检查内核参数%s..." % self.param

        if not isinstance(value, int):
            abort(ValueError, "value %s is not an integer", value)
        self.value = value

        if pass_op not in ['<', '<=', '==', '>=', '>']:
            abort(ValueError, "invalid operator %s" % pass_op)
        self.pass_op = pass_op

        if self.module == 'sunrpc':
            self.conf_file = "/etc/modprobe.d/sunrpc.conf"
            self.conf_line = "options %s %s=%s" % (
                self.module, self.param, str(self.value))
        elif self.module == 'net.ipv4':
            self.conf_file = "/etc/sysctl.conf"
            self.conf_line = "%s.%s=%s" % (
                self.module, self.param, str(self.value))
        else:
            abort(ValueError, "module %s not supported" % self.module)

    def check(self):
        (status, output) = commands.getstatusoutput(
            "sysctl -n %s.%s" % (self.module, self.param))
        if status != 0 or not output or not output.isdigit():
            # Ignore the parameter if it does not exist
            return True
        expression = output + self.pass_op + str(self.value)
        correct = eval(expression)
        if not correct:
            verbose_print ('')
        return correct

    def repair(self):
        verbose_print('')
        print(colormsg(
            "sudo sysctl -w %s.%s=%s" % (
                self.module, self.param, str(self.value)),
            colors.fg.blue))
        title = "# Aliyun NAS optimization"
        print(colormsg(
            'echo -e "\\n%s\\n%s" >> %s' % (
                title, self.conf_line, self.conf_file),
            colors.fg.blue))
        return False


class NfsMountHelper(object):
    def __init__(self):
        args_dict = self.parse_args()
        # precheck is a list of checkers to run before
        # and after mounting
        actions = self.prepare(args_dict)
        (self.mount_params, self.precheck) = actions

    def parse_args(self):
        _parser = argparse.ArgumentParser(description='阿里云NAS (NFS) - Linux客户端检查')
        _parser.add_argument('mount_target', type=str, default=None,
                             help="<server>:<path>，例如'foo%s:/'" % NAS_ALIYUN_SUFFIX)
        _parser.add_argument('local_dir', type=str, default=None,
                             help='挂载NFS文件系统的本地目录，例如/mnt')
        _parser.add_argument('-o', '--nfs_options', type=str, required=False, default='vers=4.0',
                             help='NFS挂载选项，例如vers=4.0,noresvport')
        user_options = _parser.parse_args()
        server_path_dict = MountParser.split_server_path(user_options.mount_target)
        if not server_path_dict \
           or not MountParser.is_aliyun_nas_server(server_path_dict['server']):
            abort(ValueError, """
    请以<server>:<path>格式提供挂载点地址和NAS子目录，例如：foo%s:/
    挂载点地址<server>必须以'%s'结尾，NAS子目录<path>必须以'/'开头
            """ % (NAS_ALIYUN_SUFFIX, NAS_ALIYUN_SUFFIX))
        args_dict = {}
        args_dict['mount_addr'] = server_path_dict['server']
        args_dict['export_path'] = server_path_dict['path']
        args_dict['local_dir'] = os.path.abspath(user_options.local_dir)
        args_dict['raw_opt_str'] = user_options.nfs_options
        return args_dict

    def prepare(self, args_dict):
        mount_addr = args_dict['mount_addr']
        export_path = args_dict['export_path']
        local_dir = args_dict['local_dir']
        raw_opt_str = args_dict['raw_opt_str']

        # mount_info_dict is a dict for /proc/mounts, with the key as
        # the server hostname, and the value as a list of (mountpoint,
        # path, systype, opt_str), with all tuple elements as strings
        mount_info_dict = MountParser.read_mount_info()

        precheck = []
        paramcheck = [
            KernelParamChecker(
                "sunrpc.tcp_max_slot_table_entries", 128, '>='),
            KernelParamChecker(
                "sunrpc.tcp_slot_table_entries", 128, '>='),
            KernelParamChecker(
                "net.ipv4.tcp_window_scaling", 1, '=='),
            # KernelParamChecker(
            #     "net.ipv4.tcp_sack", 1, '=='),
            KernelParamChecker(
                "net.ipv4.tcp_tw_recycle", 0, '==')
        ]

        precheck = [
            RootUserChecker(),
            KernelVersChecker(),
            MountStatusChecker(
                mount_info_dict, mount_addr,
                export_path, local_dir),
            PacManChecker(),
            NfsClientChecker(),
            PingChecker(mount_addr),
            TelnetAppChecker(),
            TimeoutChecker(mount_addr),
            TelnetChecker(mount_addr),
            PortRangeChecker(
                mount_info_dict, mount_addr),
            DirExistenceChecker(local_dir),
            DirEmptyChecker(local_dir)
        ] + paramcheck
        mount_params = {
            'raw_opt_str' : raw_opt_str,
            'mount_addr' : mount_addr,
            'export_path' : export_path,
            'local_dir' : local_dir
        }
        return (mount_params, precheck)

    def show_mount_cmd(self, mount_params):
        mount_cmd = MountParser.get_mount_cmd(**mount_params)
        if not mount_cmd:
            # Skip mounting on purpose, because it is already mounted
            return
        verbose_print(HORIZONTAL_LINE)
        print("请复制粘贴以下命令执行挂载")
        print(colormsg(mount_cmd, colors.fg.purple))

    def run(self):
        for prechecker in self.precheck:
            prechecker.run()
        self.show_mount_cmd(self.mount_params)


if __name__ == '__main__':
    verbose_print("=== 阿里云NAS (NFS) - Linux客户端检查开始 ===")
    helper = NfsMountHelper()
    helper.run()
    verbose_print("=== 阿里云NAS (NFS) - Linux客户端检查结束 ===")
