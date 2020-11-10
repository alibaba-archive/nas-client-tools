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

如果使用了AD/ACL功能，可以使用 -CheckAD $true 检查AD配置:

.\alinas_smb_windows_inspection.ps1 -MountAddress abcde-123.region-id.nas.aliyuncs.com -CheckAD $true -Userdomain "domain.com" -Username "username" -Password "password" -Locale zh-CN

如果想要配置AD/ACL，可以AD服务器上运行脚本并使用 -ConfigAD $true 配置NAS SMB所需AD信息以及生成keytab。完成后用户需上传keytab文件到NAS SMB控制台完成配置。

.\alinas_smb_windows_inspection.ps1 -MountAddress abcde-123.region-id.nas.aliyuncs.com -ConfigAD $true -CheckAD $true -Userdomain "domain.com" -Username "username" -Password "password" -Locale zh-CN

如果想要使用脚本进行挂载，可以设置 -InvokeMount $true。

.\alinas_smb_windows_inspection.ps1 -MountAddress abcde-123.region-id.nas.aliyuncs.com -InvokeMount $true -Userdomain "domain.com" -Username "username" -Password "password" -Locale zh-CN

如果想要使用脚本进行SYSTEM账号挂载，可以设置 -SystemMount $true。

.\alinas_smb_windows_inspection.ps1 -MountAddress abcde-123.region-id.nas.aliyuncs.com -SystemMount $true -Userdomain "domain.com" -Username "username" -Password "password" -Locale zh-CN


### data_coldness_analysis
#### analyze_data_coldness.py
NAS分层策略分析工具。

根据分层策略（TieringPolicies）生成每个目录下的大于等于64KB的数据的统计，包括（size, size_ratio, count, count_ratio），然后按照分层策略打印出每一层（总共dir_levels层）冷数据量（size）排名最高的几个（top_n）目录。

比如默认的分层策略是(Atime, 14-day)，则超过14天未访问的数据则为冷数据。可以配多个分层策略一次性扫描出多组结果

默认打印三层目录（dir_levels=3）。打印排序后的前两名（top_n=2）

第一层，即如果配分层策略在根目录上，>=64KB的符合分层策略的冷数据量（size），以及它的size, size_ratio, count, count_ratio

第二层，即根目录下第一层所有目录，按>=64KB的符合分层策略的冷数据量（size）排序，打印出前两名的（path，size, size_ratio, count, count_ratio）

第三层，即根目录下第二层所有目录，按>=64KB的符合分层策略的冷数据量（size）排序，打印出前两名的（path，size, size_ratio, count, count_ratio）

默认排序按照冷数据量（Size）进行排序，还可以按照SizeRatio, Count, CountRatio排序

注意：脚本为单线程扫描。如果觉得速度不够快，可以启动多个，每个扫描不同的target_dir即可

#### create_simple_coldness_data.py
生成简单的测试数据
