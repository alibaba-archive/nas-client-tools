# 阿里云NAS客户端工具

### linux_client/check_noresvport.py
检查客户端已挂载的NAS实例是否使用了noresvport参数挂载。

请下载到Linux系统的ECS客户端执行。命令格式：

python2.7 check_noresvport.py

### linux_client/monitor_alinas_nfs.py
排查客户端已挂载的NAS实例是否发生长时间阻塞，通过云监控自定义事件监控报警。

请下载到Linux系统的ECS客户端，配置crontab每分钟执行。/etc/crontab配置格式：

\* * * * * root python /opt/monitor_alinas_nfs.py 1234567 >> /var/tmp/monitor_alinas_nfs.log 2>&1

### linux_client/check_alinas_nfs_mount.py
对于指定的NFS挂载点地址和本地路径，排查相应的挂载问题。

请下载到Linux系统的ECS客户端执行。命令格式：

python2.7 check_alinas_nfs_mount.py file-system-id.region.nas.aliyuncs.com:/ /mnt

### windows_client/alinas_smb_windows_inspection.ps1
对于指定的SMB挂载点地址，排查相应的挂载问题。

请下载到Windows系统的ECS客户端执行。命令格式：

.\alinas_smb_windows_inspection.ps1 -MountAddress abcde-123.region-id.nas.aliyuncs.com -Locale zh-CN
