#!/bin/bash

# Copyright 2020-2021 Alibaba Group Holding Limited

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

outfile=$1
[ -z $outfile ] && echo "Usage: sh $0 <output_file>" && exit 1
[ -f $outfile ] && echo "Please remove file '$outfile' manually and run the script again" && exit 1

RUN_FIO=false
if [ ! -z "$2" ] && ([ "$2" = '-a' ] || [ "$2" = '--all' ]); then
    RUN_FIO=true
fi

interval=3

function run() {
    echo "" >> $outfile
    echo "Running '$1$2'" | tee -a $outfile
    if [ -z "$2" ]; then
	echo "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<" >> $outfile
	eval "$1" >> $outfile 2>&1
	echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>" >> $outfile
    elif [ "$2" = '&' ]; then
	eval "$1" >> $outfile 2>&1 &
    else
	echo "Illegal option '$2', aborting..."
	exit 1
    fi
}

# Basic Configuration
run 'uname -a'
run 'cat /etc/os-release'
run 'mount | grep aliyun'
run 'ss -nt | grep -w 2049'
run 'ss -i | grep -w nfs -A 1'
run 'sysctl -n sunrpc.tcp_slot_table_entries   # Should be 128'
run 'sysctl -n sunrpc.tcp_max_slot_table_entries   # Should be at least 128'
run 'sysctl -n net.ipv4.tcp_window_scaling    # Should be 1 to turn on TCP window scaling'
run 'sysctl -n net.ipv4.tcp_tw_recycle    # Should be 0 to turn off fast recycling of TIME-WAIT sockets'
run 'sysctl -n net.ipv4.tcp_sack   # Should be 1 to turn on SACK mode for less retransmission'

# NFS Statistics
run 'netstat -s | grep fast   # detailed info of dropped and retransmitted packets'
run 'netstat -i   # dropped packets for all ports'
run 'nfsiostat'
run 'nfsstat'
run 'mountstats -x'
run 'mountstats'

# Connectivity
run "for mtpt in \`mount | grep aliyun | awk '{print \$1}' | awk -F ':' '{print \$1}'\`; do timeout 10s bash -c \"ping -c 5 \$mtpt\"; done"
run "for dir in \`mount | grep aliyun | awk '{print \$3}'\`; do timeout 5s bash -c \"stat -f \$dir\"; done"
run "for dir in \`mount | grep aliyun | awk '{print \$3}'\`; do timeout 5s bash -c \"fuser -mv \$dir\"; done"
run 'timeout 5s bash -c "strace df -h"'

if $RUN_FIO; then
    # IO Performance and Network Quality
    for dir in `mount | grep aliyun | awk '{print $3}'`; do
	for blocksize in '1M' '4K'; do
	    for action in 'randwrite' 'randread'; do
		echo '############################################################################' | tee -a $outfile
		run "fio -numjobs=1 -iodepth=128 -direct=1 -ioengine=libaio -sync=1 -rw=$action -bs=$blocksize -size=1G -time_based -runtime=$((interval+2)) -name=Fio -directory=$dir" '&'
		sleep 1
		run "for i in {1..$interval}; do echo ''; echo '============================'; date; echo '============================'; sleep 1; done" '&'
		sleep 0.1
		run "nfsiostat $dir 1 $interval" '&'
		sleep 0.1
		run "mpstat -P ALL 1 $interval" '&'
		i=0
		while true; do
		    [ $i = $((interval)) ] && break;
		    i=$((i+1));
		    run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | wc -l'
		    run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | grep backlog | wc -l'
		    run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | grep sending | wc -l'
		    run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | grep pending | wc -l'
		    sleep 1
		done
		wait
		echo '############################################################################' | tee -a $outfile
	    done
	done
    done
    # Final Check for Network Quality
    run 'netstat -s | grep fast   # detailed info of dropped and retransmitted packets'
else
    # IO Performance and Network Quality
    run "for i in {1..$interval}; do echo ''; echo '============================'; date; echo '============================'; sleep 1; done" '&'
    sleep 0.1
    run "nfsiostat 1 $interval" '&'
    sleep 0.1
    run "mpstat -P ALL 1 $interval" '&'
    i=0
    while true; do
        [ $i = $((interval)) ] && break;
        i=$((i+1));
        run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | wc -l'
        run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | grep backlog | wc -l'
        run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | grep sending | wc -l'
        run 'cat /sys/kernel/debug/sunrpc/rpc_clnt/[0-9]/tasks | grep pending | wc -l'
        sleep 1
    done
    wait
    # Final Check for Network Quality
    run 'netstat -s | grep fast   # detailed info of dropped and retransmitted packets'
fi

echo "Scanning finished. Please send '$outfile' to the staff of Alibaba Cloud NAS Service."
