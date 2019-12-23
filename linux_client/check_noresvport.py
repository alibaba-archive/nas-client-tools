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

VERSION = '1.5'

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

import traceback

LANG = "zh_cn"

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

class intl_msg:
    def __init__(self, zh_cn, en_us):
        self.zh_cn = zh_cn
        self.en_us = en_us
    def to_lang(self, lang):
        if lang == "zh_cn":
            return self.zh_cn
        else:
            return self.en_us

GENERAL_CONTACT = intl_msg(
    "NAS研发团队（钉钉群号：23110762）",
    "NAS Development Team (DingTalk Group ID: 23110762)"
)
KERNEL_CONTACT = intl_msg(
    "NAS研发团队（钉钉群号：23177020）",
    "NAS Development Team (DingTalk Group ID: 23177020)"
)
CONTAINER_CONTACT = intl_msg(
    "NAS研发团队（钉钉群号：21906225）",
    "NAS Development Team (DingTalk Group ID: 21906225)"
)

def abort(e, msg=None):
    msg_default = intl_msg(
        "请处理以上问题，然后重新运行此脚本",
        "Please resolve the issue described above, and run this script again."
    )
    if not msg:
        msg = msg_default.to_lang(LANG)
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

def recommend_container_solution():
    msg_docker_risk = intl_msg(
            """
            如果您使用老版本的docker直接挂载NAS，请避免手动执行'docker volume rm'，该命令可能会造成数据丢失风险
            详细信息请参考文档 https://success.docker.com/article/risk-of-data-loss-when-volume-is-removed
            以下推荐步骤均不涉及此风险，请放心使用
            """,
            """
            If any dockers of old version is used to mount NAS directly, please refrain from running 'docker volume rm' manually, since it may bring in risks of data loss.
            For detailed information, please refer to this document https://success.docker.com/article/risk-of-data-loss-when-volume-is-removed
            The recommended resolutions below will not bring in risks of data loss, please feel free to follow them.
            """
    )
    msg_container_solution = intl_msg(
            """
            如果您已经使用了阿里云K8S服务和FlexVolume插件挂载NAS，推荐按以下步骤处理：
                1. 升级FlexVolume插件到最新版
                   https://help.aliyun.com/document_detail/100605.html
                2. 逐台重启所有宿主节点
                3. 在所有宿主节点上再次执行此脚本，确认整改成功
            如果您已经使用了阿里云K8S服务，但没有使用FlexVolume插件，推荐按以下步骤处理：
                1. 在NAS控制台上添加NAS挂载点
                   https://help.aliyun.com/document_detail/27531.html#title-bgs-dcm-bee
                2. 升级FlexVolume插件到最新版
                   https://help.aliyun.com/document_detail/100605.html
                3. 配置新PV，使用FlexVolume方式挂载新建的NAS挂载点
                   https://help.aliyun.com/document_detail/88940.html
                4. 将业务逐渐迁移到新PV生成的pod上
                5. 逐步废弃老的pod
                6. 在所有宿主节点上再次执行此脚本，确认整改成功
                7. 禁用老的NAS挂载点
                8. 确认业务不受影响，正常运行
                9. 删除老的NAS挂载点
            如果您使用的是其他容器管理系统，推荐按以下步骤处理：
                1. 新建Kubernetes托管版集群
                   https://help.aliyun.com/document_detail/95108.html
                2. 在新建的K8S集群上，使用FlexVolume插件挂载现有NAS挂载点
                   https://help.aliyun.com/document_detail/88940.html
                3. 将业务逐步迁移到新的K8S集群上
                4. 确认业务在新的K8S集群上运行正常
                5. 在新K8S集群的所有宿主节点上再次执行此脚本，确认通过
                6. 逐步废弃老的容器系统
            以上三种方法，均需要v1.10.4-dfe877b或更新版本的FlexVolume插件，挂载NAS时会自带noresvport参数，是最方便的处理方法
            如果您希望考虑其他方法，请参考文档 https://yq.aliyun.com/articles/707169 处理，如有疑问请联系%s
            """,
            """
            If you are already using the Container Service for Kubernetes (ACK) of Alibaba Cloud and the FlexVolume plug-in to mount NAS volumes, we recommend the following resolution:
                1. Upgrade the FlexVolume plug-in to the latest version.
                   https://www.alibabacloud.com/help/doc-detail/100605.htm
                2. Restart all the nodes for containers one-by-one.
                3. Run this script again on all the nodes, to make sure they pass the check.
            If you are using the Container Service for Kubernetes (ACK) of Alibaba Cloud, we recommend the following resolution:
                1. Add a mount target on the NAS console.
                   https://www.alibabacloud.com/help/doc-detail/27531.htm#title-bgs-dcm-bee
                2. Upgrade the FlexVolume plug-in to the latest version.
                   https://www.alibabacloud.com/help/doc-detail/100605.htm
                3. Create a new PV that uses FlexVolume to mount the new NAS mount target.
                   https://www.alibabacloud.com/help/doc-detail/88940.htm
                4. Gradually migrate your workload onto the new pods generated by the new PV.
                5. Gradually desert the old pods.
                6. Run this script again on all the nodes, to make sure they pass the check.
                7. Disable the old mount target.
                8. Make sure the workload is not affected and runs normally.
                9. Delete the old mount target.
            If you are using any other container management systems, we recommend the following resolution:
                1. Create a managed cluster of Container Service for Kubernetes.
                   https://www.alibabacloud.com/help/doc-detail/95108.htm
                2. On the new Kubernetes cluster, use FlexVolume to mount the existing NAS mount target.
                   https://www.alibabacloud.com/help/doc-detail/88940.html
                3. Gradually migrate your workload onto the new Kubernetes cluster.
                4. Make sure the workload runs normally on the new Kubernetes cluster.
                5. Run this script again on all the nodes of the new cluster, to make sure they pass the check.
                6. Gradually desert the old container management system.
            The three methods above both use the FlexVolume plug-in of version v1.10.4-dfe877b or newer, which sets the noresvport option automatically when mounting a NAS volume, and these are the simplest resolutions available.
            If you want to consider any other resolutions, please contact %s
            """
    )
    print(colormsg(
        msg_docker_risk.to_lang(LANG),
        colors.fg.orange))
    print(colormsg(
        msg_container_solution.to_lang(LANG) % CONTAINER_CONTACT.to_lang(LANG),
        colors.fg.cyan))


class MountParser:
    @staticmethod
    def is_aliyun_nas_server(server):
        msg_skip_extreme = intl_msg(
            "目前此脚本还不支持极速型NAS挂载排查，跳过自动检查",
            "The script does not yet support Speed NAS, will skip automatic check."
        )
        if server.endswith(NAS_ALIYUN_EXTREME_SUFFIX):
            print(colormsg(
                msg_skip_extreme.to_lang(LANG),
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
        msg_format_error = intl_msg(
            "%s的格式异常，请联系%s",
            "Unexpected format of %s, please contact %s"
        )
        mount_status = mount_line.split()
        if len(mount_status) != 6:
            abort(OSError,
                  msg_format_error.to_lang(LANG) % (
                      MOUNT_FILENAME, GENERAL_CONTACT.to_lang(LANG)))
        mount_status_dict = {}
        mount_status_dict['target'] = mount_status[0]
        mount_status_dict['mountpoint'] = mount_status[1]
        mount_status_dict['systype'] = mount_status[2]
        mount_status_dict['opt_str'] = mount_status[3]
        return mount_status_dict

    @staticmethod
    def recommend_mount_options(raw_opt_str):
        msg_recommend_vers = intl_msg(
            "阿里云NAS不支持vers=%s，自动改成vers=%s挂载",
            "Alibaba Cloud NAS does not support vers=%s, will use vers=%s for mounting."
        )
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
                msg_recommend_vers.to_lang(LANG) % (
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
        msg_linux_only = intl_msg(
            "请注意此脚本只适用于Linux系统",
            "This script can only be run on Linux systems."
        )
        try:
            mount_file = open(MOUNT_FILENAME, 'r')
        except IOError as e:
            abort(e, msg_linux_only.to_lang(LANG))

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
        msg_sys_port_occupied = intl_msg(
            "现存NFS连接占用了以下系统端口：",
            "The existing NFS connections has occupied the following system ports: "
        )
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
                msg_sys_port_occupied.to_lang(LANG) + \
                ','.join(occupied_sys_port_list),
                colors.fg.orange))
        return no_sys_port_occupied

    @staticmethod
    def parse_fuser_output(local_dir):
        msg_fuser_installation = intl_msg(
                  """
                  fuser工具不存在，请选择以下命令安装
                  CentOS/RedHat：yum install -y psmisc
                  Debian/Ubuntu：apt-get --yes install psmisc
                  安装后再次运行脚本，如果仍然失败，请联系%s
                  """,
                  """
                  'fuser' could not be found, please install it with the following command:
                  CentOS/RedHat: yum install -y psmisc
                  Debian/Ubuntu: apt-get --yes install psmisc
                  Please run the script again after installation, and if the script failed again, please contact %s
                  """
        )
        if not run_cmd("which fuser"):
            abort(OSError,
                  msg_fuser_installation.to_lang(LANG) % GENERAL_CONTACT.to_lang(LANG))
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
    FAIL_MSG = intl_msg(
        "解决以上问题之后，请重新运行此脚本继续排查",
        "Please run the script again to continue checking, after the issues above are resolved."
    )

    def check(self):
        return False

    def prompt(self):
        return True

    def repair(self):
        verbose_print('')
        return False

    def alarm_upgrade_kernel(self, kernel_version):
        msg_kernel_resolution = intl_msg(
            """
            内核版本%s存在已知缺陷
            缺陷详情请参考文档 https://help.aliyun.com/document_detail/114129.html
            请按照以下步骤处理：
                1. 购买新版内核的ECS
                2. 在新ECS上挂载现有NAS文件系统
                3. 将业务逐步迁移到新的ECS上
                4. 确认业务在新的ECS上运行正常
                5. 逐步废弃老的ECS
            请注意，升级ECS内核风险较大，我们不推荐这种做法。如果您坚持选择升级ECS内核，请充分评估升级内核对于相关业务及应用兼容性的风险，并且在升级前创建ECS快照以备不时之需
            如果仍有疑问，请联系%s
            """,
            """
            The kernel version %s has some known issues.
            Please refer to this document for detailed information https://www.alibabacloud.com/help/doc-detail/114129.htm
            Please follow the instructions below for a work-around:
                1. Create an ECS instance with the latest kernel version.
                2. Mount the existing NAS file system onto the new ECS instance.
                3. Gradually migrate the workload to the new ECS instance.
                4. Make sure the workload runs normally on the new ECS instance.
                5. Gradually desert the old ECS instance.
            Please note there is considerable risk when upgrading the ECS kernel, and we do not recommend you to do so. If you have decided to upgrade the kernel, please evaluate the risks involved for your workload and the compatiblity of your applications, and prepare a snapshot of the ECS for the probable emergency.
            If you have any questions, please contact %s
            """
        )
        print(colormsg(
            msg_kernel_resolution.to_lang(LANG) % (
                kernel_version,
                KERNEL_CONTACT.to_lang(LANG)),
            colors.fg.cyan))

    def alarm_unmount_server(self, mount_info_dict, mount_addr):
        msg_remaining_shell = intl_msg(
            "还有shell没退出曾经挂载过NFS文件系统的目录，如无法找到请重启机器后再挂载",
            "There are remaining shell processes visiting paths mounted with NFS file systems, please reboot the ECS if they could not be found, before the NFS file systems are mounted again."
        )
        msg_warn_offpeak = intl_msg(
            """
            以下操作建议在业务低峰期进行
            """,
            """
            Please wait for off-peak hours and follow the instructions below.
            """
        )
        msg_ecs_resolution = intl_msg(
            """
            建议将以下步骤复制保存后再执行操作
            请卸载所有使用挂载点%s的本地目录，再使用noresvport参数重新挂载：
                1. 停止以下所有对挂载路径进行操作的进程（如果没有请跳过），评估业务影响后，使用kill -9 <PID>停止进程
                        %s
                2. 卸载所有相关挂载路径，如果返回“device is busy”，请确认上一步的所有进程已经被kill，并且所有相关容器已被停止
                        sudo umount %s
                3. 确认所有相关挂载路径完成卸载，以下命令应该返回为空
                        mount | grep %s
                4. 确认所有相关TCP连接已被回收，以下命令应该返回为空（如有残留连接，说明卸载前仍有进程或容器使用NAS，建议重启机器）
                        ss -nt | grep ESTAB | grep -w 2049 | grep %s
                5. 执行以下命令，重新挂载所有目录（挂载命令已经加入noresvport）
                        %s
            如果重新挂载出现相同问题，可能是遇到了客户端Linux的缺陷，请择机重启机器后再挂载。如有疑问，请联系%s
            """,
            """
            We recommend you save the following instructions before running the commands.
            Please unmount all paths mounted with the mount target %s, and mount them again with the 'noresvport' option:
                1. Stop all processes that access the mounted paths (skip if none is shown below), and after evaluating possible outcomes, please run 'kill -9 <PID>' to stop the processes.
                        %s
                2. Unmount all relevant paths, and if the command returns 'device is busy', please make sure all the processes shown in the last step are killed, and all related containers are stopped.
                        sudo umount %s
                3. Make sure all relevant paths are unmounted, and the following command returns nothing.
                        mount | grep %s
                4. Make sure all relevant TCP connections are recycled, and the following command returns nothing (if there are remaining connections, it may be caused by unstopped processes or containers accessing NAS before it was unmounted, and we recommend rebooting the ECS).
                        ss -nt | grep ESTAB | grep -w 2049 | grep %s
                5. Run the following commands to re-mount all the paths ('noresvport' already included in the commands below).
                        %s
            If the same issue persist after re-mounting, it is probably caused by a bug in the Linux kernel on the client side, please reboot ECS and try mounting again. If you have any questions, please contact %s
            """
        )

        if mount_addr not in mount_info_dict \
           or not mount_info_dict[mount_addr]:
            print(colormsg(
                msg_remaining_shell.to_lang(LANG),
                colors.fg.cyan))
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
            msg_warn_offpeak.to_lang(LANG), colors.fg.orange) + colormsg(
            msg_ecs_resolution.to_lang(LANG) % (
                mount_addr,
                delimiter.join(fuser_str_list),
                ' '.join(mountpoint_list),
                mount_addr,
                get_ip_of_hostname(mount_addr),
                delimiter.join(mount_cmd_list),
                GENERAL_CONTACT.to_lang(LANG)),
            colors.fg.cyan)
        print(warning_msg)

    def run(self):
        msg_pass = intl_msg("通过", "PASS")
        msg_prompt_fail = intl_msg(
            "用户选择结束脚本，请手动解决上述问题后，再次运行此脚本继续排查其他问题",
            "The user has chosen to terminate the script. Please manually fix the issue above, and run the script again to check other issues."
        )
        try:
            verbose_print(HORIZONTAL_LINE)
            if self.CHECK_MSG:
                verbose_print(self.CHECK_MSG.to_lang(LANG), newline=False)
                sys.stdout.flush()
            check_passed = self.check()
            if not check_passed:
                prompt_passed = self.prompt()
                if prompt_passed:
                    if self.REPAIR_MSG:
                        verbose_print(self.REPAIR_MSG.to_lang(LANG), newline=False)
                        sys.stdout.flush()
                    repair_passed = self.repair()
                    if repair_passed:
                        verbose_print(colormsg(
                            msg_pass.to_lang(LANG), self.PASS_COLOR))
                        return repair_passed
                    else:
                        if self.FAIL_MSG:
                            verbose_print(colormsg(
                                self.FAIL_MSG.to_lang(LANG), self.FAIL_COLOR))
                        if self.EXIT_ON_FAIL:
                            sys.exit(1)
                        return repair_passed
                else:
                    print(colormsg(
                        msg_prompt_fail.to_lang(LANG),
                        self.FAIL_COLOR))
                    if self.EXIT_ON_FAIL:
                        sys.exit(1)
                    return prompt_passed
            else:
                verbose_print(colormsg(msg_pass.to_lang(LANG), self.PASS_COLOR))
                return check_passed
        except Exception as e:
            traceback.print_exc()
            abort(e)

class RootUserChecker(ConditionChecker):
    CHECK_MSG = intl_msg(
        "正在检查root操作权限...",
        "Checking root permission..."
    )
    REPAIR_MSG = intl_msg(
        "请使用sudo再次运行此脚本",
        "Please run the script again with 'sudo'."
    )

    def check(self):
        msg_root_permission = intl_msg(
                """
                此脚本需要使用root权限执行
                """,
                """
                This script requires root permission to run.
                """
        )
        if os.geteuid() != 0:
            verbose_print('')
            print(colormsg(
                msg_root_permission.to_lang(LANG),
                colors.fg.cyan))
        return os.geteuid() == 0


class KernelVersChecker(ConditionChecker):
    CHECK_MSG = intl_msg(
        "正在检查系统内核版本...",
        "Checking kernel version..."
    )
    REPAIR_MSG = intl_msg(
        "当前内核版本存在已知问题",
        "The kernel version has some known issues."
    )

    def vers_compare(self, str1, str2):
        list1 = str1.split('.')
        list2 = str2.split('.')
        head1 = list1[0]
        head2 = list2[0]
        if (not head1) and (not head2):
            return 0
        elif not head1:
            return -1
        elif not head2:
            return 1
        digit1 = int(head1) if head1.isdigit() else 0
        digit2 = int(head2) if head2.isdigit() else 0
        if digit1 == digit2:
            return self.vers_compare('.'.join(list1[1:]), '.'.join(list2[1:]))
        else:
            return digit1 - digit2

    def check(self):
        msg_os_unsupported = intl_msg(
            "阿里云NAS的NFS文件系统目前只支持Linux和Windows挂载，不支持macOS或类似系统挂载",
            "Currently the NFS file systems of Alibaba Cloud NAS can only be mounted by Linux or Windows, and cannot be mounted by macOS or other operating systems."
        )
        sysname = platform.system()
        version = platform.release()
        self.kernel_version = version

        # Only Linux is supported
        if sysname != "Linux":
            abort(OSError, msg_os_unsupported.to_lang(LANG))

        # Parse kernel version into major and minor by '-'
        if '-' in version:
            (major, minor) = version.split('-', 1)
        else:
            major = version
            minor = ''

        # Check if the kernel version is known to have problems
        bad_kernels = {
            '4.2.0': ('18', '19'),
            '3.10.0' : ('', '229.11.1'),
            '2.6.32' : ('696', '696.10.1')
        }
        if major in bad_kernels \
           and self.vers_compare(minor, bad_kernels[major][0]) >= 0 \
           and self.vers_compare(minor, bad_kernels[major][1]) < 0:
            verbose_print('')
            return False
        return True

    def repair(self):
        verbose_print('')
        self.alarm_upgrade_kernel(self.kernel_version)
        return False


class StatChecker(ConditionChecker):
    EXIT_ON_FAIL = False
    CHECK_MSG = intl_msg(
        "正在检查挂载的NFS文件系统能否联通...",
        "Checking if the NFS file system is responsive..."
    )
    REPAIR_MSG = intl_msg(
        "挂载的NFS文件系统无法联通",
        "The mounted NFS file system is not responsive."
    )
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
    CHECK_MSG = intl_msg(
        "正在检查挂载选项是否包含noresvport...",
        "Checking if the mount options contain 'noresvport'..."
    )
    REPAIR_MSG = intl_msg(
        "挂载选项没有包含noresvport",
        "The mount options do not contain 'noresvport'."
    )
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
    CHECK_MSG = intl_msg(
        "正在检查NFS连接是否使用了noresvport参数...",
        "Checking if 'noresvport' is effective on the NFS connections..."
    )
    REPAIR_MSG = intl_msg(
        "现存NFS连接没有使用noresvport参数",
        "'noresvport' has not taken effect on the NFS connections."
    )
    FAIL_MSG = ""

    def __init__(self, mount_info_dict,
                 mount_addr):
        self.mount_info_dict = mount_info_dict
        self.mount_addr = mount_addr

    def check(self):
        msg_ss_missing = intl_msg(
            "ss工具不存在，请联系%s",
            "'ss' could not be found, please contact %s"
        )
        if not run_cmd("which ss"):
            abort(OSError, msg_ss_missing.to_lang(LANG) % GENERAL_CONTACT.to_lang(LANG))
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
    CHECK_MSG = intl_msg(
        "正在综合检查挂载点的noresvport是否生效...\n",
        "Starting comprehensive check on whether 'noresvport' has taken effect on the mount target...\n"
    )
    REPAIR_MSG = intl_msg(
        "挂载点没有使用noresvport参数",
        "'noresvport' has not taken effect on the mount target."
    )
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
        msg_unfound_mount_target = intl_msg(
            "挂载点%s无法在%s中找到，请联系%s",
            "The mount target %s could not be found in %s, please contact %s"
        )
        msg_removed_mount_target = intl_msg(
            "挂载点%s疑似已被删除，请登录NAS控制台确认已删除，然后在业务低峰期转移相关任务，并且卸载本地目录：umount -l %s",
            "The mount target %s may have been deleted, please log on to the NAS console, make sure it is deleted, then migrate the relevant workload during off-peak hours, and unmount the paths: umount -l %s"
        )
        msg_remount_needed = intl_msg(
            "挂载点地址%s需要使用noresvport重新挂载",
            "Mount target %s needs to be re-mounted with 'noresvport'."
        )

        if not self.mount_tuple_list:
            # Ignore the mount address if it has not been mounted
            return True

        ip = get_ip_of_hostname(self.mount_addr)

        if ip is None:
            if self.mount_addr not in self.mount_info_dict:
                abort(ValueError, msg_unfound_mount_target.to_lang(LANG) % (
                    self.mount_addr, MOUNT_FILENAME, GENERAL_CONTACT.to_lang(LANG)))
            mount_tuple_list = self.mount_info_dict[self.mount_addr]
            mountpoint_list = []
            for mount_tuple in mount_tuple_list:
                mountpoint_list.append(mount_tuple[0])
            print(colormsg(
                msg_removed_mount_target.to_lang(LANG) % (
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
                msg_remount_needed.to_lang(LANG) % self.mount_addr,
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
    CHECK_MSG = intl_msg(
        "正在检查是否存在残留的坏连接...",
        "Checking if there is any bad connections remaining..."
    )
    REPAIR_MSG = intl_msg(
        "存在需要重启修复的残留连接",
        "There are remaining bad connections that needs to be recycled by rebooting ECS."
    )
    FAIL_MSG = ""

    def __init__(self, mount_info_dict, need_repair):
        self.mount_info_dict = mount_info_dict
        self.need_repair = need_repair

    def check(self):
        msg_remain_connections = intl_msg(
            "存在残留的NFS连接没有使用noresvport参数，可能是卸载NAS前，相关进程或容器没有全部停止，或触发了Linux的内核缺陷。为了避免后续挂载复用此连接，请在业务低峰期重启ECS回收残留连接，解决此问题",
            "There are remaining NFS connections with 'noresvport' not in effect, which may caused by unstopped processes or containers accessing NAS before it was unmounted, or caused by a bug in the Linux kernel. To avoid future mounts from reusing this connection, please wait for off-peak hours and reboot the ECS to recycle the connections and resolve this issue."
        )
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
                msg_remain_connections.to_lang(LANG),
                colors.fg.red))
        return no_sys_port_occupied

    def repair(self):
        msg_fix_connections = intl_msg(
            """
            存在残留的NFS连接没有使用noresvport参数，请重启ECS解决此问题
            """,
            """
            There are remaining NFS connections with 'noresvport' not in effect, please reboot the ECS to resolve this issue.
            """
        )
        verbose_print('')
        if self.need_repair:
            print(colormsg(
                msg_fix_connections.to_lang(LANG),
                colors.fg.cyan))
        return False


class NfsMountHelper(object):
    def __init__(self):
        args_dict = self.parse_args()
        self.need_repair = args_dict['need_repair']
        self.container_repair = args_dict['container_repair']
        self.check_list = self.prepare(args_dict)

    def parse_args(self):
        global LANG
        global VERBOSE
        _parser = argparse.ArgumentParser(description="Alibaba Cloud NAS (NFS) - Linux Client Scan for 'noresvport'")
        _parser.add_argument("-e", "--english", help="run the script in English",
                             action="store_true")
        _parser.add_argument("-v", "--verbose", help="display all items to check",
                             action="store_true")
        _parser.add_argument("-r", "--repair", help="display resolution for ECS",
                             action="store_true")
        _parser.add_argument("-c", "--container", help="display resolution for containers",
                             action="store_true")
        user_options = _parser.parse_args()
        args_dict = {}
        if user_options.english:
            LANG = "en_us"
        VERBOSE = user_options.verbose
        args_dict['need_repair'] = user_options.repair
        args_dict['container_repair'] = user_options.container
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
        msg_success = intl_msg(
            "本台ECS无须处理noresvport问题",
            "There is no issue for 'noresvport' on this ECS"
        )
        msg_ecs_detail = intl_msg(
            "如果您正使用ECS直接挂载NAS，请使用-r参数重新执行此脚本，查看详细解决方案",
            "If NAS is mounted directly to ECS, please run the script again with the '-r' option, for detailed resolution."
        )
        msg_container_detail = intl_msg(
            "如果您正使用容器挂载NAS，请使用-c参数重新执行此脚本，查看详细解决方案",
            "If NAS is mounted to containers, please run the script again with the '-c' option, for detailed resolution."
        )
        msg_error = intl_msg(
            "请处理本台ECS的noresvport问题，完毕之后请再次运行此脚本，确认风险排除",
            "Please resolve the 'noresvport' issue on this ECS, and run the script again to make sure there are no more risks."
        )

        all_good = True
        for checker in self.check_list:
            all_good &= checker.run()
        if all_good:
            print(colormsg(
                msg_success.to_lang(LANG),
                colors.fg.green))
        else:
            if not self.need_repair and not self.container_repair:
                print(colormsg(
                    msg_ecs_detail.to_lang(LANG),
                    colors.fg.orange))
            if not self.container_repair:
                print(colormsg(
                    msg_container_detail.to_lang(LANG),
                    colors.fg.orange))
            else:
                recommend_container_solution()
            print(colormsg(
                msg_error.to_lang(LANG),
                colors.fg.orange))


if __name__ == '__main__':
    verbose_print("=== Alibaba Cloud NAS (NFS) - Linux Client Scan for 'noresvport' starts ===")
    helper = NfsMountHelper()
    helper.run()
    verbose_print("=== Alibaba Cloud NAS (NFS) - Linux Client Scan for 'noresvport' ends ===")
