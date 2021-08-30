<#PSScriptInfo

.VERSION 1.0

.GUID 12a35fe8-f826-4e16-8027-617ca1aa015f

.AUTHOR Xuzi Zhou

.COMPANYNAME Alibaba Group Holding Limited

.COPYRIGHT (c) 2019-2020 Alibaba Group Holding Limited

.TAGS
Alibaba_Cloud
Aliyun
NAS
SMB
Windows

.LICENSEURI https://www.github.com/alibabacloudnas/nas-client-tools/LICENSE

.PROJECTURI https://www.github.com/alibabacloudnas/nas-client-tools

.ICONURI

.EXTERNALMODULEDEPENDENCIES

.REQUIREDSCRIPTS

.EXTERNALSCRIPTDEPENDENCIES

.RELEASENOTES
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

.PRIVATEDATA

#>

<#
.SYNOPSIS
    Test NAS (SMB protocol) service compatibility and detect connection problems
.DESCRIPTION
    1. Run alinas_smb_windows_inspection powershell script to detect:
     a. The NAS (SMB protocol) compatibility of the local computer
     b. Server roles and features that might affect the performance of NAS (SMB protocol)
     c. Connection problems regarding the provided mount target address
    2. The script will try to fix the issues found

    Usage example:
      .\alinas_smb_windows_inspection.ps1 -MountAddress abcde-123.region-id.nas.aliyuncs.com -Locale zh-CN
#>

param (
    # Specify the mount target address to test in the format of "<MOUNT_TARGET_ID>.<REGION_ID>.nas.aliyuncs.com"
    [string]$MountAddress = "",
    # Default is "auto", put "zh-CN" to output messages in Chinese
    [string]$Locale = "auto",
    # Check NAS SMB AD/ACL setup. Default is $false
    [bool]$CheckAD = $false,
    # Config NAS SMB AD/ACL setup. Default is $false
    # Official doc: https://help.aliyun.com/document_detail/154930.html
    [bool]$ConfigAD = $false,
    # Mount as SYSTEM account. 
    # Reference: https://developer.aliyun.com/article/775050
    [bool]$InvokeMount = $false,
    [bool]$SystemMount = $false,
    [string]$Username = "",
    [string]$Userdomain = "",
    [string]$Password = "",
    [string]$SetspnNas = "alinas"
)

function Get-ReferenceUrls()
{
    $urls = @{
        AlinasSmbFaq = "https://help.aliyun.com/document_detail/112011.html";
        AlibabaCloudSmbFaq = "https://www.alibabacloud.com/help/doc-detail/112011.html";
        AliyunChinaSupport = "https://cn.aliyun.com/service";
        AlibabaCloudIntlSupport = "https://www.alibabacloud.com/services";
        MsftSmbGuestAccess = "https://support.microsoft.com/en-us/help/4046019";
    }
    return $urls
}

function Get-CmdFormats()
{
    $cmds = @{
        NetUse = "net use Z: \\{0}\myshare";
        Mklink = "mklink /D C:\myshare \\{0}\myshare";
        CmdOverPs = "cmd.exe /c `"{0}`"";
    }
    return $cmds
}

function Get-LocaleMessages([string]$localeChoice)
{
    $messagesEn = @{
        # Header strings
        Header = "Alibaba Cloud Network Attached Storage (SMB) - Windows Client Inspection";
        DocAddr = "* Instructions for script usage: {0}";
        MissingMountTarget = "* Note: use -MountAddress option to provide a mount target address`n       in the format of {0}";
        DisplayMountTarget = "* Mount Target Address: {0}";
        # Footer strings
        Question = "If you have any questions, please contact Alibaba Cloud Support.`n China Site: {0}`n International Site: {1}";
        EnterToExit = "Press Enter to exit...";
        # Common tags
        Warning = "  !WARNING!  ";
        Error = " !!ERROR!! ";
        Or = "or";
        # Checkpoint strings
        Pass = "{0} ...Pass";
        Attention = "{0} ...Attention";
        Fail = "{0} ...Fail";
        SysReqNotMet = "Alibaba Cloud NAS SMB protocol requires clients running {0} ({1}) or newer systems";
        CurrSys = "Current system version: {0} ({1})";
        CheckRoles = "Check server roles and features";
        CheckServices = "Check local services";
        CheckNetComponents = "Check network components";
        CheckMountTarget = "Check mount target: {0}";
        InvokeMountTarget = "Mount: {0}";
        # Next step strings
        NextStep = "The following {0} action(s) are recommended:";
        NoNextStep = "No suggested actions at this point.";
        NextCommand = "Try to fix with following {0} commands:";
        RunCommand = "Run following command: {0}";
        IgnoreCommand = "Ignore running command: {0}";
        RunCommandFailed = "Run command: {0} failed";
        Yes = "Yes";
        No = "No";
        NsSysReqNotMet = "Access NAS (SMB protocol) from {0} ({1}) or newer systems";
        NsNoGuestAccess = "Guest auth is required to access SMB NAS file system, please configure the Registry value: `n{0}`n   See Microsoft support document for details:`n     {1}";
        NsServiceNotRunning = "Key local services not running. Please search and run `"services.msc`", then start the following service(s):`n{0}";
        NsServiceNotRunningTpl = "   - Service: {0}";
        NsLanmanNotInProviderOrder = "LanmanWorkstation is not set in ProviderOrder registry. Add LanmanWorkstation to the Registry entry:`n{0}";
        NsHasNfsService = "The installed NFS services may affect the performance of SMB NAS file system. If you do not need NFS service, please consider:`n{0}";
        NsHasNfsService1 = "   - Remove '{0}' role from the system";
        NsHasNfsService2 = "   - Delete Nfsnp from the Registry entry:`n{0}";
        NsMissingNetComponents = "Key network components not installed. Please install the following component(s):`n{0}";
        NsMissingNetComponentsMsclient = "   - Client for Microsoft Networks (ms_msclient)";
        NsMissingNetComponentsMsserver = "   - File and Printer Sharing for Microsoft Networks (ms_server)";
        NsDisabledNetComponents = "Key network components disabled. Please enable the following component(s):`n{0}";
        NsCorrectMountTarget = "Please provide correct mount target address (format: {0})";
        NsBadConnection = "Failed to ping {0}, possible reasons are:`n   - mount target address typo`n   - client and mount target are not in the same VPC`n   - something is wrong with inter-VPC or VPN connection`n   - something is wrong with DNS service";
        NsBadSmbConnection = "NAS SMB service is not available via mount target ({0}), please double-check mount point address";
        NoAvailableDriveLetter = "All drive letters from a to z are occupied. Please release some and try again";
        NotADDomainController = "Not AD domain controller. Ignore ADDC checkings";
        UserDomainShouldHaveParts = "Userdomain: {0} should have . splitted parts like abc.def.org";
        ADDomainMismatch = "ADDomain mismatch: AD domain: {0}, user input domain: {1}";
        IncorrectADUsernameOrPassword = "Incorrect AD username or password. Input username: {0}, input password: {1}";
        IncorrectSetSpn = "Incorrect setspn {0} result";
        CorrectSetSpn = "To setspn correctly, please refer to: https://help.aliyun.com/document_detail/154930.html";
        SetSpnLessThanTwoLines = "setspn result: {0}, less than 2 lines";
        UnexpectedSetSpnFirstLine = "setspn result: {0}, first line: {1} is not: Registered ServicePrincipalNames for CN={2},DC=domain,DC=subdomain,...,DC=com";
        NoCifsMountAddress = "setspn result doesn't have cifs/{0}";
        StartADControllerCheck = "Start ADController checking";
        EndADControllerCheck = "ADController checking is completed. AD domain name, username and setspn result are correct. If mount failed or identity authentication failed, it could be keytab errors. Please refer to: https://help.aliyun.com/document_detail/154930.html";
        StartADClientCheck = "Start ADClient checking";
        PingADDomainFailed = "This client failed to ping AD domain, possibly due to DNS issue. DNS should include route to ADController. Current DNS: {0}";
        KerbeorsPortFailed = "Kerberos port TCP 88 cannot be connected. ADDomain: {0}";
        LDAPPortFailed = "LDAP port TCP 389 cannot be connected. ADDomain: {0}";
        LDAPGlobalCatalogPortFailed = "LDAPGlobalCatalog port TCP 3268 cannot be connected. ADDomain: {0}";
        EndADClientCheck = "ADClient checking is completed. AD domain name, username are correct. If mount failed or identity authentication failed, it could be keytab errors. Please refer to: https://help.aliyun.com/document_detail/154930.html";
        StartSettingADController = "Start setting ADController. Following official doc: https://help.aliyun.com/document_detail/154930.html";
        EmptyDomainForADControllerSettings = "AD domain is empty. Cannot config ADController";
        ConfigADControllerManuallyFor2008R2 = "2008R2 AD Controller setup is complicated, please follow the official doc to setup manually";
        InstallADDSFailed = "Install ADDS feature failed";
        InstallDNSFailed = "Install DNS feature failed";
        InstallADDSandDNSFailed = "Install ADDS and DNS roles failed";
        InstallADDSForestFailed = "Install ADDS forest failed. Failed to create AD domain";
        GenerateKeytabFailed = "Generate keytab failed. MountAddress: {0}, ADDomain: {1}";
        EndSettingADController = "Finish setting ADController. Please upload keytab file c:\nas-mount-target.keytab to NAS console to finish connecting AD and NAS SMB. After that you can use AD user to mount NAS SMB";
        StartSystemMount = "Start SYSTEM mount. Reference: https://developer.aliyun.com/article/775050";
        EmptyUserinfoForSystemMountOnWin2016OrLater = "Empty Username or Password input for SYSTEM mount on Windows 2016 or later. Fail to proceed";
        CreateMyMountBatFailed = "Create my_mount.bat file failed";
        RunSystemMountTaskFailed = "Run SYSTEM mount task failed";
        CreateSystemMountTaskFailed = "Create SYSTEM mount task failed";
        EndSystemMount = "Finish SYSTEM mount";
        SkipSystemMount = "SYSTEM mount is skipped because MountAddress: {0} is invalid";
        SkipMount = "Mount is skipped because MountAddress: {0} is invalid";
        SkipNextCommands = "Total fixing commands: {0}, executed commands: {1}. {2} number of fixing commands are skipped to execute";
        PrintException = "An error occurred: `n{0}`nException:`n{1}";
        PrintEncodingError = "`n!! NOTICE: console output encoding has been changed to {0}`n- Run the following command to recover original console output encoding {1}:`n`t[System.Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding({2})";
        # Mount suggestions
        MountFailSuggestion = "* Note: common reasons for SMB NAS file system mount failures are:`n   1) network connectivity`n   2) unsupported client system version or settings`n   3) try to mount a NFS NAS as an SMB NAS`n   4) inproper NAS permission group settings`n   5) an overdue account";
        MountFailDoc = "  View detailed solutions in official documentation:`n   {0}";
        # Mount instructions
        FixGuestAccessFirst = "* Before running the following mount commands, please follow recommended action to allow guest access to SMB";
        FixLocalServices = "* Before running the following mount commands, please follow recommended action to start key local services via services.msc";
        FixNetComponents = "* Before running the following mount commands, please follow recommended action to enable key network components";
        MountHelpDoc = "* If fails to mount, please find solutions in document: {0}`n";
        MountRef = "Please refer to the following example commands to mount your SMB NAS file system:";
        MountRefNetUse = " - Mount SMB NAS file system to a volume label (Z: in the example command):";
        MountRefMklink = "`n - Mount SMB NAS file system as a sub-directory (symbolic link to C:\myshare in the example command):";
        PsMklinkWarning = "    * Note: since mklink is not a PowerShell cmdlet and requires administrative privileges , please run command in Command Prompt (cmd.exe) as Administrator";
        CmdCommandPromptAdmin = "    Admin: Command Prompt> ";
        CmdPowershellAdmin = "    Admin: PowerShell> ";
        CmdBoth = "   PowerShell or Command Prompt> ";
        # Mount target format
        MountTargetTpl = "<MOUNT_TARGET_ID>.<REGION_ID>.nas.aliyuncs.com";
    }
    $messagesCn = @{
        # Header strings
        Header = "阿里云文件存储 NAS (SMB 协议) - Windows客户端状态检查";
        DocAddr = "* 脚本使用文档: {0}";
        MissingMountTarget = "* 提示: 如需检查挂载点可用性，请使用 -MountAddress选项提供挂载点地址`n       地址格式为 {0}";
        DisplayMountTarget = "* 挂载点地址: {0}";
        # Footer strings
        Question = "如有疑问，请联系阿里云支持中心。`n 中国站: {0}`n 国际站: {1}";
        EnterToExit = "请按回车键退出...";
        # Common tags
        Warning = "  !注意!  ";
        Error = " !!错误!! ";
        Or = "或者";
        # Checkpoint strings
        Pass = "{0} ...通过";
        Attention = "{0} ...注意";
        Fail = "{0} ...未通过";
        SysReqNotMet = "阿里云文件存储 NAS SMB 协议文件系统要求客户端运行{0} ({1})或更新版本的操作系统";
        CurrSys = "当前系统版本: {0} ({1})";
        CheckServices = "检查相关系统本地服务";
        CheckRoles = "检查相关系统角色与服务";
        CheckNetComponents = "检查相关网络组件";
        CheckMountTarget = "检查挂载点: {0}";
        InvokeMountTarget = "挂载: {0}";
        # Next step strings
        NextStep = "推荐进行以下{0}个操作:";
        NoNextStep = "暂时没有推荐的下一步操作。";
        NextCommand = "尝试运行以下{0}个命令进行修复:";
        RunCommand = "运行以下命令: {0}";
        IgnoreCommand = "忽略该命令: {0}, 不运行";
        RunCommandFailed = "运行命令: {0} 失败";
        Yes = "是";
        No = "否";
        NsSysReqNotMet = "使用{0} ({1})或更新版本的操作系统访问 SMB 协议 NAS 文件系统";
        NsNoGuestAccess = "需要系统允许通过 Guest 身份访问 NAS，请修改注册表项: `n{0}`n   详见微软官方支持文档:`n     {1}";
        NsServiceNotRunning = "关键系统本地服务并未启动，请搜索并运行`"services.msc`"，然后启动以下服务:`n{0}";
        NsServiceNotRunningTpl = "   - 服务: {0}";
        NsLanmanNotInProviderOrder = "LanmanWorkstation并未在注册表中正确配置。请在以下注册表项中添加 LanmanWorkstation:`n{0}";
        NsHasNfsService = "系统中已安装的 NFS 相关服务可能影响 SMB 协议 NAS 的性能。如果您并不需要 NFS 服务，请考虑:`n{0}";
        NsHasNfsService1 = "   - 从服务器角色中移除'{0}'";
        NsHasNfsService2 = "   - 在以下注册表项中删除 Nfsnp:`n{0}";
        NsMissingNetComponents = "关键网络组件并未安装，请安装以下组件:`n{0}";
        NsMissingNetComponentsMsclient = "   - Microsoft 网络客户端 (ms_msclient)";
        NsMissingNetComponentsMsserver = "   - Microsoft 网络的文件和打印机共享 (ms_server)";
        NsDisabledNetComponents = "关键网络组件未启用，请启用以下组件:`n{0}";
        NsCorrectMountTarget = "请提供正确格式的挂载点地址 (格式: {0})";
        NsBadConnection = "Ping 挂载点失败 ({0})，请检查下列可能的问题:`n   - 挂载点地址拼写错误`n   - 客户端与挂载点不在同一个 VPC`n   - 跨 VPC 连接或 VPN 连接存在问题`n   - DNS 服务故障，请检查配置";
        NsBadSmbConnection = "挂载点未发现 NAS SMB 服务 ({0})，请检查挂载点地址";
        NoAvailableDriveLetter = "盘符a-z都被占用. 请释放任意盘符后再重试";
        NotADDomainController = "不是AD服务器, 跳过AD服务器设置检查";
        ADDomainMismatch = "ADDomain不匹配: ADDomain: {0}, 用户输入Domain: {1}";
        UserDomainShouldHaveParts = "用户AD域: {0}, 需要有.分段，类似abc.def.org";
        IncorrectADUsernameOrPassword = "AD用户名或密码不正确. 用户名: {0}, 密码: {1}";
        IncorrectSetSpn = "setspn {0} 命令结果不正确";
        CorrectSetSpn = "正确setspn配置请参考: https://help.aliyun.com/document_detail/154930.html";
        SetSpnLessThanTwoLines = "setspn输出结果: {0}, 行数小于2";
        UnexpectedSetSpnFirstLine = "setspn结果: {0}, 第一行: {1} 不等于: Registered ServicePrincipalNames for CN={2},DC=domain,DC=subdomain,...,DC=com";
        NoCifsMountAddress = "setspn结果不包含cifs/{0}";
        StartADControllerCheck = "开始AD服务端配置检查";
        EndADControllerCheck = "AD服务端配置检查结束. AD域名, 用户名, setspn配置正常. 如果挂载失败或者身份认证错误, 可能是keytab生成或者上传出错. 请参考: https://help.aliyun.com/document_detail/154930.html";
        StartADClientCheck = "开始AD客户端配置检查";
        PingADDomainFailed = "客户端Ping不到AD域, 连接不成功. 可能是DNS问题. DNS需能连接到ADController. DNS: {0}";
        KerbeorsPortFailed = "Kerberos接口TCP 88无法连接. AD域: {0}";
        LDAPPortFailed = "LDAP接口TCP 389无法连接. AD域: {0}";
        LDAPGlobalCatalogPortFailed = "LDAPGlobalCatalog接口TCP 3268无法连接. AD域: {0}";
        EndADClientCheck = "AD客户端检查结束。AD域名、用户名正常。如果挂载失败或者身份认证错误，可能是keytab生成或者上传出错。请参考: https://help.aliyun.com/document_detail/154930.html";
        StartSettingADController = "开始配置ADController. 参考官方文档: https://help.aliyun.com/document_detail/154930.html";
        EmptyDomainForADControllerSettings = "AD域名为空，无法配置ADController";
        ConfigADControllerManuallyFor2008R2 = "2008R2 AD控制器安装比较复杂，请参考官方文档步骤自行配置";
        InstallADDSFailed = "安装ADDS功能失败";
        InstallDNSFailed = "安装DNS功能失败";
        InstallADDSandDNSFailed = "安装ADDS和DNS角色失败";
        InstallADDSForestFailed = "安装ADDS森林失败. 创建AD域失败";
        GenerateKeytabFailed = "生成keytab失败. 挂载点: {0}, AD域名: {1}";
        EndSettingADController = "完成ADController设置. 请上传keytab文件c:\nas-mount-target.keytab到控制台, 完成AD与NAS SMB的连接. 之后即可使用AD身份挂载NAS SMB";
        StartSystemMount = "开始SYSTEM账号挂载. 参考文档: https://developer.aliyun.com/article/775050";
        EmptyUserinfoForSystemMountOnWin2016OrLater = "Userdomain或者Username或者Password为空, 导致Windows2016或者更新版本无法SYSTEM挂载";
        CreateMyMountBatFailed = "创建my_mount.bat文件失败";
        RunSystemMountTaskFailed = "运行SYSTEM挂载启动任务失败";
        CreateSystemMountTaskFailed = "创建SYSTEM挂载启动任务失败";
        EndSystemMount = "完成SYSTEM挂载";
        SkipSystemMount = "跳过SYSTEM挂载，因为MountAddress: {0} 不合法";
        SkipMount = "跳过挂载，因为MountAddress: {0} 不合法";
        SkipNextCommands = "总修复命令数: {0}, 已运行修复命令数: {1}. {2} 个修复命令跳过执行";
        PrintException = "发生错误: `n{0}`n异常Exception:`n{1}";
        PrintEncodingError = "`n!! 注意: 控制台输出编码变成了 {0}`n- 运行下面代码将输出编码还原为 {1}:`n`t[System.Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding({2})";
        # Mount suggestions
        MountFailSuggestion = "* 提示: SMB协议文件系统挂载失败的常见原因为:`n   1) 网络不通`n   2) 客户端系统版本或设置问题`n   3) 错以SMB文件系统挂载方式挂载NFS文件系统`n   4) NAS权限组设置问题`n   5) NAS服务欠费";
        MountFailDoc = "  详见相关官方文档: {0}";
        # Mount instructions
        FixGuestAccessFirst = "* 运行以下命令之前，请先按推荐操作修改注册表以允许通过 Guest 身份访问 NAS";
        FixLocalServices = "* 运行以下命令之前，请先按推荐操作启动关键系统本地服务";
        FixNetComponents = "* 运行以下命令之前，请先按推荐操作启用关键网络组件";
        MountHelpDoc = "* 如果依旧挂载失败，请参考帮助文档排查: {0}`n";
        MountRef = "请参考以下命令挂载 SMB 协议 NAS 文件系统:";
        MountRefNetUse = " - 挂载 SMB 协议 NAS 文件系统到盘符 (命令范例中为 Z:):";
        MountRefMklink = "`n - 挂载 SMB 协议 NAS 文件系统到子目录 (命令范例中为指向 C:\myshare 的符号链接):";
        PsMklinkWarning = "    * 注意: mklink并不是一个PowerShell指令且需要管理员权限，需以管理员身份使用命令提示符 (cmd.exe) 运行";
        CmdCommandPromptAdmin = "    管理员: 命令提示符> ";
        CmdPowershellAdmin = "    管理员: PowerShell> ";
        CmdBoth = "    PowerShell 或 命令提示符> ";
        # Mount target format
        MountTargetTpl = "<文件卷挂载点ID>.<地域ID>.nas.aliyuncs.com";
    }
    if ($localeChoice -eq "zh-CN")
    {
        return $messagesCn
    }
    else
    {
        return $messagesEn
    }
}

function Get-LastWindowsSystemAllowsGuest()
{
    $lastWinSys = @{
        Caption = "Microsoft Windows Server 2016";
        Version = "10.0.14393";
        VersionObj = New-Object -TypeName System.Version -ArgumentList "10.0.14393.0"
    }
    return $lastWinSys
}

function Get-MinWindowsSystem()
{
    $minWinSys = @{
        Caption = "Microsoft Windows Server 2008 R2";
        Version = "6.1.7601";
        VersionObj = New-Object -TypeName System.Version -ArgumentList "6.1.7601.65536"
    }
    return $minWinSys
}

function Compare-SystemVersionsMinor([System.Version]$first, [ScriptBlock]$comp, [System.Version]$second)
{
    $firstVer = New-Object -TypeName System.Version -ArgumentList $first.Major,$first.Minor
    $secondVer = New-Object -TypeName System.Version -ArgumentList $second.Major,$second.Minor
    return (Invoke-Command -ScriptBlock $comp -arg $firstVer,$secondVer)
}

function Compare-SystemVersionsBuild([System.Version]$first, [ScriptBlock]$comp, [System.Version]$second)
{
    $firstVer = New-Object -TypeName System.Version -ArgumentList $first.Major,$first.Minor,$first.Build
    $secondVer = New-Object -TypeName System.Version -ArgumentList $second.Major,$second.Minor,$second.Build
    return (Invoke-Command -ScriptBlock $comp -arg $firstVer,$secondVer)
}

function Add-NextStep([string]$content)
{
    [void]$nextSteps.Add($content)
}

function Add-NextCommand([string]$command)
{
    [void]$nextCommands.Add($command)
}

function Check-SystemRequirement()
{
    $sysInfo = Get-WmiObject Win32_OperatingSystem
    $sysVer = [System.Environment]::OSVersion.Version

    $lt = {$args[0] -lt $args[1]}
    $eq = {$args[0] -eq $args[1]}
    $gt = {$args[0] -gt $args[1]}

    # Check minimum system version requirement
    $minSysInfo = Get-MinWindowsSystem
    $minSysVer = $minSysInfo.VersionObj
    if (Compare-SystemVersionsMinor $sysVer $lt $minSysVer)
    {
        $failMsg = $messages.Fail -f ($messages.CurrSys -f $sysInfo.Caption, $sysInfo.Version)
        Write-Host $failMsg -ForegroundColor Red
        $sysReqNotMetStr = $messages.SysReqNotMet -f $minSysInfo.Caption, $minSysInfo.Version
        Write-Host $messages.Warning -ForegroundColor Red -NoNewLine
        Write-Host $sysReqNotMetStr -ForegroundColor Red
        Add-NextStep ($messages.NsSysReqNotMet -f $minSysInfo.Caption, $minSysInfo.Version)
        return $false
    }
    $passMsg = $messages.Pass -f ($messages.CurrSys -f $sysInfo.Caption, $sysInfo.Version)
    Write-Host $passMsg -ForegroundColor Green

    # Check registry preventing guest mounting in newer systems
    $lastGuestSysInfo = Get-LastWindowsSystemAllowsGuest
    $lastGuestSysVer = $lastGuestSysInfo.VersionObj
    if (Compare-SystemVersionsBuild $sysVer $gt $lastGuestSysVer)
    {
        $registryPath = "Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters"
        $registryName = "AllowInsecureGuestAuth"
        $registryObj = Get-ItemProperty -Path $registryPath
        $allowGuest = $registryObj.$registryName
        if ($allowGuest -eq $null -Or $allowGuest -ne 1 )
        {
            $command = ""
            if ($allowGuest -eq $null)
            {
                $value = "null"
                $command = "New-ItemProperty -Path {0} -Name {1} -PropertyType {2} -Value {3}" -f $registryPath, $registryName, "DWORD", 1
            }
            else
            {
                $value = "$allowGuest"
                $command = "Set-ItemProperty -Path {0} -Name {1} -Value {2}" -f $registryPath, $registryName, 1
            }
            $failMsg = $messages.Fail -f ("[{0}] {1}: {2}" -f $registryPath, $registryName, $value)
            Write-Host $failMsg -ForegroundColor Red
            Add-NextStep ($messages.NsNoGuestAccess -f ("    [{0}]`n    {1}=REG_DWORD:1" -f $registryPath, $registryName), $references.MsftSmbGuestAccess)
            Add-NextCommand $command
            $global:regeditNeeded = $true
            return $true
        }
        $passMsg = $messages.Pass -f ("[{0}] {1}: {2}" -f $registryPath, $registryName, "$allowGuest")
        Write-Host $passMsg -ForegroundColor Green
    }
    return $true
}

# Windows 2008 does not have Test-NetConnection
function Test-RemotePort([string]$computerName, [int]$port)
{
    try
    {
        $ip = [System.Net.Dns]::GetHostAddresses($computerName) | select-object IPAddressToString -ExpandProperty  IPAddressToString
        if($ip.GetType().Name -eq "Object[]")
        {
            $ip = $ip[0]
        }
    } catch
    {
        return $false
    }
    $tcpClient = New-Object Net.Sockets.TcpClient
    try
    {
        $tcpClient.Connect($ip, $port)
    }
    catch
    {
        return $false
    }

    if($tcpClient.Connected)
    {
        $tcpClient.Close()
        return $true
    }
    return $false
}

function Check-MountTarget()
{
    if ($MountAddress -eq "")
    {
        return $false
    }

    $MountAddress = $MountAddress.Trim()
    $passMsg = $messages.Pass -f ($messages.CheckMountTarget -f $MountAddress)
    $failMsg = $messages.Fail -f ($messages.CheckMountTarget -f $MountAddress)
    # Validate mount target format
    if (-Not ($MountAddress -imatch "^[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+\.nas\.aliyuncs\.com$"))
    {
        Write-Host $failMsg -ForegroundColor Red
        Add-NextStep ($messages.NsCorrectMountTarget -f $messages.MountTargetTpl)
        return $false
    }
    # Check mount target connection
    $pingTest = Test-Connection -ComputerName $MountAddress -Quiet
    # Mount target is not accessible (wrong addr, DNS problem, VPC)
    if (-Not $pingTest)
    {
        Write-Host $failMsg -ForegroundColor Red
        Add-NextStep ($messages.NsBadConnection -f $MountAddress)
        return $false
    }
    # Check SMB port
    $smbTest = Test-RemotePort $MountAddress 445
    if ($smbTest)
    {
        Write-Host $passMsg -ForegroundColor Green
        return $true
    }
    Add-NextStep ($messages.NsBadSmbConnection -f $MountAddress)
    Write-Host $failMsg -ForegroundColor Red
    return $false
}

function Get-DriveLetter()
{
    $Drives = Get-ChildItem -Path Function:[a-z]: -Name
    for ($i = $Drives.count - 1; $i -ge 0; $i--) {
        if (-Not (Test-Path -Path $Drives[$i])){
            return $Drives[$i]
        }
    }
    return ""
}

function Invoke-MountTarget()
{
    $passMsg = $messages.Pass -f ($messages.InvokeMountTarget -f $MountAddress)
    $failMsg = $messages.Fail -f ($messages.InvokeMountTarget -f $MountAddress)
    $driveLetter = Get-DriveLetter
    if ($driveLetter -eq "")
    {
        Write-Host $messages.NoAvailableDriveLetter -ForegroundColor Red
        Write-Host $failMsg -ForegroundColor Red
        return $false
    }
    if ($Username -eq "")
    {
        $command = "net use {0} \\{1}\myshare" -f $driveLetter, $MountAddress
    }
    elseif ($Userdomain -eq "")
    {
        $domainFull = (Get-WmiObject Win32_ComputerSystem).Domain
        if ($Password -eq "")
        {
            $command = "net use {0} \\{1}\myshare /user:{2}\{3}" -f $driveLetter, $MountAddress, $domainFull, $Username
        }
        else
        {
            $command = "net use {0} \\{1}\myshare /user:{2}\{3} {4}" -f $driveLetter, $MountAddress, $domainFull, $Username, $Password
        }
    }
    else
    {
        if (-Not (Check-Userdomain))
        {
            return $false
        }
        if ($Password -eq "")
        {
            $command = "net use {0} \\{1}\myshare /user:{2}\{3}" -f $driveLetter, $MountAddress, $Userdomain, $Username
        }
        else
        {
            $command = "net use {0} \\{1}\myshare /user:{2}\{3} {4}" -f $driveLetter, $MountAddress, $Userdomain, $Username, $Password
        }
    }

    if (-Not (Invoke-PromptCommand $command))
    {
        Write-Host $failMsg -ForegroundColor Red
        return $false
    }

    Write-Host $passMsg -ForegroundColor Green
    return $true
}

function New-SystemMountTaskAndRun()
{
    $command = 'schtasks /create /tn "my_mount" /tr "c:\my_mount.bat" /sc onstart /RU SYSTEM /RL HIGHEST; schtasks /run /tn "my_mount"'
    if (-Not (Invoke-PromptCommand $command))
    {
        Write-Host $messages.CreateSystemMountTaskFailed -ForegroundColor Red
        return $false
    }
    return $true
}

function Invoke-SystemMount()
{
    Write-Host $messages.StartSystemMount -ForegroundColor Green

    $driveLetter = Get-DriveLetter
    if ($driveLetter -eq "")
    {
        Write-Host $messages.NoAvailableDriveLetter -ForegroundColor Red
        Write-Host $failMsg -ForegroundColor Red
        return $false
    }

    $myMountBat = ""
    # For 2016 or later, add /user password
    $sysInfo = Get-WmiObject Win32_OperatingSystem
    $sysVer = [System.Environment]::OSVersion.Version
    $lastGuestSysInfo = Get-LastWindowsSystemAllowsGuest
    $lastGuestSysVer = $lastGuestSysInfo.VersionObj
    $gt = {$args[0] -gt $args[1]}
    if (Compare-SystemVersionsBuild $sysVer $gt $lastGuestSysVer)
    {
        if ($Username -eq "" -Or $Password -eq "")
        {
            Write-Host $messages.EmptyUserinfoForSystemMountOnWin2016OrLater -ForegroundColor Red
            return $false
        }
        $domainFull = (Get-WmiObject Win32_ComputerSystem).Domain
        if ($Userdomain -ne "" -And (Check-Userdomain))
        {
            $domainFull = $Userdomain
        }
        $myMountBat = @" 
ECHO ON  
ECHO This will map the drive, but is being run by task scheduler AS the user SYSTEM  
ECHO which should make it accessible to the user SYSTEM  
ECHO List the existing drives first.

net use >> c:\SystemNetUseOutput.txt
net use {0} \\{1}\myshare /user:{2}\{3} {4}

ECHO List the existing drives with the new mapping

net use >> c:\SystemNetUseOutput.txt

ECHO See what user this batch job ran under  

whoami >> c:\SystemNetUseOutput.txt

ECHO need to exit to allow the job to finish
EXIT
"@ -f $driveLetter, $MountAddress, $domainFull, $Username, $Password
    }
    else
    {
        $myMountBat = @" 
ECHO ON  
ECHO This will map the drive, but is being run by task scheduler AS the user SYSTEM  
ECHO which should make it accessible to the user SYSTEM  
ECHO List the existing drives first.  

net use >> c:\SystemNetUseOutput.txt  
net use {0} \\{1}\myshare

ECHO List the existing drives with the new mapping

net use >> c:\SystemNetUseOutput.txt  

ECHO See what user this batch job ran under  

whoami >> c:\SystemNetUseOutput.txt  

ECHO need to exit to allow the job to finish  
EXIT
"@ -f $driveLetter, $MountAddress
    }

    $command = "Set-Content -Path `"c:\my_mount.bat`" -Value `"$myMountBat`""
    if (-Not (Invoke-PromptCommand $command))
    {
        Write-Host $messages.CreateMyMountBatFailed -ForegroundColor Red
    }

    try
    {
        $result = Get-ScheduledTaskInfo "my_mount"
        if ($result.TaskName -eq "my_mount")
        {
            $command = 'schtasks /run /tn "my_mount"'
            if (-Not (Invoke-PromptCommand $command))
            {
                Write-Host $messages.RunSystemMountTaskFailed -ForegroundColor Red
                return $false
            }
        }
        elseif (-Not (New-SystemMountTaskAndRun))
        {
            return $false
        }
    }
    catch
    {
        if (-Not (New-SystemMountTaskAndRun))
        {
            return $false
        }
    }

    Write-Host $messages.EndSystemMount -ForegroundColor Green
    return $true
}

function Set-ADControllerSettings()
{
    Write-Host $messages.StartSettingADController -ForegroundColor Green

    if ($Userdomain -eq "")
    {
        Write-Host $messages.EmptyDomainForADControllerSettings -ForegroundColor Red
        return $false
    }
    if (-Not (Check-Userdomain))
    {
        return $false
    }

    $domainFull = (Get-WmiObject Win32_ComputerSystem).Domain

    if ($domainFull -eq "WORKGROUP")
    {
        $sysInfo = Get-WmiObject Win32_OperatingSystem
        $sysVer = [System.Environment]::OSVersion.Version

        $eq = {$args[0] -eq $args[1]}

        # Check if it is 2008 R2
        $minSysInfo = Get-MinWindowsSystem
        $minSysVer = $minSysInfo.VersionObj
        if (Compare-SystemVersionsMinor $sysVer $eq $minSysVer)
        {
            Write-Host $messages.ConfigADControllerManuallyFor2008R2 -ForegroundColor Red
            return $false
        }
        else
        {
            if (-Not (Get-WindowsFeature AD-Domain-Services).Installed)
            {
                $command = "Install-WindowsFeature AD-Domain-Services -IncludeManagementTools"
                if (-Not (Invoke-PromptCommand $command))
                {
                    Write-Host $messages.InstallADDSFailed -ForegroundColor Red
                    return $false
                }
            }
            if (-Not (Get-WindowsFeature DNS).Installed)
            {
                
                $command = "Install-WindowsFeature DNS -IncludeManagementTools"
                if (-Not (Invoke-PromptCommand $command))
                {
                    Write-Host $messages.InstallDNSFailed -ForegroundColor Red
                    return $false
                }
            }
        }

        try
        {
            Get-ADDomainController
        }
        catch
        {
            $command = "Install-ADDSForest -InstallDns -DomainName $Userdomain"
            if (-Not (Invoke-PromptCommand $command))
            {
                Write-Host $messages.InstallADDSForestFailed -ForegroundColor Red
                return $false
            }
        }
    }
    elseif ($domainFull -ne $Userdomain)
    {
        Write-Host ($messages.ADDomainMismatch -f $domainFull, $Userdomain) -ForegroundColor Red
        return $false
    }

    try
    {
        Get-ADUser $SetspnNas
    }
    catch
    {
        $domainParts = $Userdomain.Split(".")
        $command = "dsadd user CN=$SetspnNas"
        for ($i = 0; $i -lt $domainParts.count; $i++)
        {
            $part = $domainParts[$i]
            $command += ",DC=$part"
        }
        $command += " -samid $SetspnNas -display `"Alibaba Cloud NAS Service Account`" -pwd tHePaSsWoRd123 -pwdneverexpires yes"
        if (-Not (Invoke-PromptCommand $command))
        {
            Write-Host $messages.DsaddUserAlinasFailed -ForegroundColor Red
            return $false
        }
    }

    if (-Not (Check-SetSpnAlinas $domainFull))
    {
        $command = "setspn -S cifs/$MountAddress $SetspnNas"
        if (-Not (Invoke-PromptCommand $command))
        {
            Write-Host ($messages.SetspnCifsAlinasFailed -f $MountAddress) -ForegroundColor Red
            return $false
        }
    }
    $domainFullUpper = $domainFull.ToUpper()
    $command = "ktpass -princ cifs/$MountAddress@$domainFullUpper -ptype KRB5_NT_PRINCIPAL -mapuser $SetspnNas@$domainFull -crypto All -out c:\nas-mount-target.keytab -pass tHePaSsWoRd123"
    Invoke-PromptCommand $command -ignoreError $true
    if (-Not (Test-Path "c:\nas-mount-target.keytab"))
    {
        Write-Host ($messages.GenerateKeytabFailed -f $MountAddress, $domainFull) -ForegroundColor Red
        return $false
    }

    Write-Host $messages.EndSettingADController -ForegroundColor Yellow
    return $true
}

function Check-Userdomain()
{
    if ($Userdomain -ne "" -And $Userdomain.Split(".").count -le 1)
    {
        Write-Host ($messages.UserDomainShouldHaveParts -f $Userdomain) -ForegroundColor Red
        return $false
    }

    return $true
}

function Check-SetSpnAlinas([string]$domainFull)
{
    $domainParts = $domainFull.Split(".")
    try
    {
        $result = Invoke-Expression "setspn $SetspnNas"
        $lines = $result.Split("`n")
        if ($lines.count -lt 2)
        {
            Write-Host ($messages.SetSpnLessThanTwoLines -f $result) -ForegroundColor Red
            Add-NextStep $messages.CorrectSetSpn
            return $false
        }
        for ($i = 0; $i -lt $domainParts.count; $i++)
        {
            $part = $domainParts[$i]
            if (-Not $lines[0].contains("CN=$SetspnNas") -Or -Not $lines[0].contains("DC=$part"))
            {
                Write-Host ($messages.UnexpectedSetSpnFirstLine -f $result, $lines[0], $SetspnNas) -ForegroundColor Red
                Add-NextStep $messages.CorrectSetSpn
                return $false
            }
        }
        $found = $false
        for ($i = 1; $i -lt $lines.count; $i = $i + 1)
        {
            if ($lines[$i].Trim() -like "cifs/$MountAddress")
            {
                $found = $true
                break
            }
        }
        if (-Not $found)
        {
            Write-Host ($messages.NoCifsMountAddress -f $result) -ForegroundColor Red
            Add-NextStep $messages.CorrectSetSpn
            return $false
        }
    }
    catch
    {
        Write-Host ($messages.IncorrectSetSpn -f $SetspnNas) -ForegroundColor Red
        Add-NextStep $messages.CorrectSetSpn
        return $false
    }

    return $true
}

function Check-ADControllerSettings()
{
    Write-Host $messages.StartADControllerCheck -ForegroundColor Green

    $domainFull = ""
    try
    {
        $result = Get-ADDomainController
        $domainFull = $result.Domain
    }
    catch
    {
        Write-Host $messages.NotADDomainController -ForegroundColor Red
        return $false
    }

    if (-Not (Check-Userdomain))
    {
        return $false
    }

    if ($domainFull -ne $Userdomain)
    {
        Write-Host ($messages.ADDomainMismatch -f $domainFull, $Userdomain) -ForegroundColor Red
        return $false
    }

    try
    {
        [securestring]$secStringPassword = ConvertTo-SecureString $Password -AsPlainText -Force
        [pscredential]$credObject = New-Object System.Management.Automation.PSCredential ("$Userdomain\$Username", $secStringPassword)
        Get-AdUser -Identity $Username -Credential $credObject
    }
    catch
    {
        Write-Host ($messages.IncorrectADUsernameOrPassword -f "$Userdomain\$Username", $Password) -ForegroundColor Red
        return $false
    }

    if (-Not (Check-SetSpnAlinas $domainFull))
    {
        return $false
    }

    Write-Host $messages.EndADControllerCheck -ForegroundColor Green
    return $true
}

function Check-ADDomain([string]$domainFull)
{
    if ($domainFull -ne "WORKGROUP")
    {
        if (-Not (Check-Userdomain))
        {
            return $false
        }
        if ($domainFull -ne $Userdomain)
        {
            Write-Host ($messages.ADDomainMismatch -f $domainFull, $Userdomain) -ForegroundColor Red
            return $false
        }
    }
    elseif ($Userdomain -ne "")
    {
        try
        {
            $result = Test-Connection $Userdomain
        }
        catch
        {
            Write-Host ($messages.PingADDomainFailed -f (Convert-String Get-DnsClientServerAddress)) -ForegroundColor Red
            return $false
        }
        if (-Not (Check-ADPorts $Userdomain))
        {
            return $false
        }
    }
    elseif (-Not (Check-ADPorts $domainFull))
    {
        return $false
    }

    return $true
}

function Check-ADPorts([string]$domainFull)
{
    $kerberosTest = Test-RemotePort $domainFull 88
    if (-Not $kerberosTest)
    {
        Write-Host ($messages.KerbeorsPortFailed -f $domainFull) -ForegroundColor Red
        return $false
    }

    $ldapTest = Test-RemotePort $domainFull 389
    if (-Not $ldapTest)
    {
        Write-Host ($messages.LDAPPortFailed -f $domainFull) -ForegroundColor Red
        return $false
    }

    $ldapGlobalCalalogTest = Test-RemotePort $domainFull 3268
    if (-Not $ldapGlobalCalalogTest)
    {
        Write-Host ($messages.LDAPGlobalCatalogPortFailed -f $domainFull) -ForegroundColor Red
        return $false
    }

    return $true
}

function Check-ADClientSettings()
{
    Write-Host $messages.StartADClientCheck -ForegroundColor Green

    $domainFull = (Get-WmiObject Win32_ComputerSystem).Domain
    if (-Not (Check-ADDomain $domainFull))
    {
        return $false
    }

    Write-Host $messages.EndADClientCheck -ForegroundColor Green
    return $true
}

function Check-NfsService()
{
    # Don't auto fix nfs service as the impact of nfs service to smb service is still a myth.
    $actionString = ""

    try
    {
        Import-Module ServerManager -ErrorAction SilentlyContinue

        # Check FS-NFS-Service* role
        $nfsServices = Get-WindowsFeature FS-NFS-Service*
        if ($nfsServices.Count -gt 0 -And $nfsServices[0].Installed)
        {
            $actionString = $messages.NsHasNfsService1 -f $nfsServices[0].DisplayName
            $command = "Uninstall-WindowsFeature FS-NFS-Service"
            # Add-NextCommand $command
        }
        # Check NFS-Client feature
        $nfsClient = Get-WindowsFeature NFS-Client
        if ($nfsClient.Count -gt 0 -And $nfsServices[0].Installed)
        {
            if ($actionString -ne "")
            {
                $actionString += "`n"
            }
            $actionString += $messages.NsHasNfsService1 -f $nfsClient[0].DisplayName
            $command = "Uninstall-WindowsFeature NFS-Client"
            # Add-NextCommand $command
        }
    }
    catch
    {
        # Win 10 does not have ServerManager
        $nfsClient = Get-WindowsOptionalFeature -Online -FeatureName ClientForNFS-Infrastructure
        if ($nfsClient.Count -gt 0 -And $nfsServices.State -eq "Enabled")
        {
            if ($actionString -ne "")
            {
                $actionString += "`n"
            }
            $actionString += $messages.NsHasNfsService1 -f $nfsClient[0].DisplayName
            $command = "Disable-WindowsOptionalFeature -Online -FeatureName ClientForNFS-Infrastructure"
            # Add-NextCommand $command
        }
    }

    # Check registry
    $registryPath = "Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\NetworkProvider\Order"
    $registryName = "ProviderOrder"
    $registryObj = Get-ItemProperty -Path $registryPath
    $npOrder = $registryObj.$registryName
    if ($npOrder -imatch "nfsnp")
    {
        $registryString = "      [{0}]`n      {1}=REG_SZ:{2}" -f $registryPath, $registryName, $npOrder
        if ($actionString -ne "")
        {
            $actionString += "`n"
        }
        $actionString += $messages.NsHasNfsService2 -f $registryString
        $npOrder = $npOrder -replace "nfsnp,","" -replace ",nfsnp",""
        $npOrder = "`"$nporder`""
        $command = "Set-ItemProperty -Path {0} -Name {1} -Value {2}" -f $registryPath, $registryName, $npOrder
        # Add-NextCommand $command
    }
    if ($actionString -ne "")
    {
        $attentionMsg = $messages.Attention -f $messages.CheckRoles
        Write-Host $attentionMsg -ForegroundColor Yellow
        Add-NextStep ($messages.NsHasNfsService -f $actionString)
    }
    else
    {
        $passMsg = $messages.Pass -f $messages.CheckRoles
        Write-Host $passMsg -ForegroundColor Green
    }
}

function Check-LocalServices()
{
    # LanmanWorkstation: Workstation service
    # lmhosts: TCP/IP netBIOS Helper service
    $serviceNames = @("LanmanWorkstation","lmhosts")
    $servicesToStart = [System.Collections.ArrayList]@()

    foreach ($srv in $serviceNames)
    {
        $localService = Get-Service -Name $srv
        if ($localService.Status -ne "Running")
        {
            [void]$servicesToStart.Add($localService.Name)
        }
    }

    if ($servicesToStart.Count -gt 0)
    {
        $actionString = ""
        foreach ($srvName in $servicesToStart)
        {
            if ($actionString -ne "")
            {
                $actionString += "`n"
            }
            $actionString += $messages.NsServiceNotRunningTpl -f $srvName
            $command = "Set-Service -Name $srvName -Status Running"
            Add-NextCommand $command
        }
        Add-NextStep ($messages.NsServiceNotRunning -f $actionString)
        $global:localServiceNeeded = $true
    }

    $registryPath = "Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\NetworkProvider\Order"
    $registryName = "ProviderOrder"
    $registryObj = Get-ItemProperty -Path $registryPath
    $npOrder = $registryObj.$registryName
    if (-Not ($npOrder -imatch "LanmanWorkstation"))
    {
        $actionString = ""
        $registryString = "      [{0}]`n      {1}=REG_SZ:{2}" -f $registryPath, $registryName, $npOrder
        Add-NextStep ($messages.NsLanmanNotInProviderOrder -f $registryString)
        if ($npOrder -eq "")
        {
            $npOrder = "LanmanWorkstation"
        }
        else
        {
            $npOrder += ",LanmanWorkstation"
            $npOrder = "`"$nporder`""
        }
        $command = "Set-ItemProperty -Path {0} -Name {1} -Value {2}" -f $registryPath, $registryName, $npOrder
        Add-NextCommand $command
        $global:lanmanNotInProviderOrder = $true
    }

    if ($global:localServiceNeeded -Or $global:lanmanNotInProviderOrder)
    {
        $failMsg = $messages.Fail -f $messages.CheckServices
        Write-Host $failMsg -ForegroundColor Red
    }
    else
    {
        $passMsg = $messages.Pass -f $messages.CheckServices
        Write-Host $passMsg -ForegroundColor Green
    }
}

function Check-NetComponent()
{
    # ms_msclient: Client for Microsoft Networks
    # ms_server: File and Printer Sharing for Microsoft Networks
    $actionString = ""
    $componentList = netcfg -s n
    if (-Not ($componentList -imatch "ms_msclient"))
    {
        $actionString += $messages.NsMissingNetComponentsMsclient
    }
    if (-Not ($componentList -imatch "ms_server"))
    {
        if ($actionString -ne "")
        {
            $actionString += "`n"
        }
        $actionString += $messages.NsMissingNetComponentsMsserver
    }

    if ($actionString -ne "")
    {
        $failMsg = $messages.Fail -f $messages.CheckNetComponents
        Write-Host $failMsg -ForegroundColor Red
        Add-NextStep ($messages.NsMissingNetComponents -f $actionString)
        $global:netComponentNeeded = $true
    }
    else
    {
        # check if components are enabled, not supported in windows 2008r2
        try
        {
            $components = Get-NetAdapterBinding
        }
        catch
        {
            $components = [System.Collections.ArrayList]@()
        }
        foreach ($comp in $components)
        {
            if (($comp.ComponentID -eq "ms_msclient") -And (-Not $comp.Enabled))
            {
                if ($actionString -ne "")
                {
                    $actionString += "`n"
                }
                $actionString += $messages.NsMissingNetComponentsMsclient
            }
            if (($comp.ComponentID -eq "ms_server") -And (-Not $comp.Enabled))
            {
                if ($actionString -ne "")
                {
                    $actionString += "`n"
                }
                $actionString += $messages.NsMissingNetComponentsMsserver
            }
        }
        if ($actionString -ne "")
        {
            $failMsg = $messages.Fail -f $messages.CheckNetComponents
            Write-Host $failMsg -ForegroundColor Red
            Add-NextStep ($messages.NsDisabledNetComponents -f $actionString)
            $global:netComponentNeeded = $true
        }
        else
        {
            $passMsg = $messages.Pass -f $messages.CheckNetComponents
            Write-Host $passMsg -ForegroundColor Green
        }
    }
}

function Print-Header()
{
    Write-Host ("`n=== {0} ===" -f $messages.Header)
    if ($MountAddress -eq "")
    {
        Write-Host ($messages.MissingMountTarget -f $messages.MountTargetTpl) -ForegroundColor Yellow
        exit 1
    }
    else
    {
        Write-Host ($messages.DisplayMountTarget -f $MountAddress)
    }
    Write-Host ""
}

function Print-HorizontalLine()
{
    Write-Host "------------------------------------------"
}

function Print-MountCommands()
{
    Write-Host $messages.MountRef -ForegroundColor Cyan
    if ($global:regeditNeeded)
    {
        Write-Host $messages.FixGuestAccessFirst -ForegroundColor Red
    }
    if ($global:localServiceNeeded)
    {
        Write-Host $messages.FixLocalServices -ForegroundColor Red
    }
    if ($global:netComponentNeeded)
    {
        Write-Host $messages.FixNetComponents -ForegroundColor Red
    }
    if ($localeChoice -eq "zh-CN")
    {
        Write-Host ($messages.MountHelpDoc -f $references.AlinasSmbFaq) -ForegroundColor Yellow
    }
    else
    {
        Write-Host ($messages.MountHelpDoc -f $references.AlibabaCloudSmbFaq) -ForegroundColor Yellow
    }

    Write-Host $messages.MountRefNetUse -ForegroundColor Cyan
    $netUseCmd = $cmdFormats.NetUse -f $MountAddress
    Write-Host $messages.CmdBoth -ForegroundColor Cyan -NoNewLine
    Write-Host $netUseCmd -ForegroundColor Gray

    Write-Host $messages.MountRefMklink -ForegroundColor Cyan
    Write-Host $messages.PsMklinkWarning -ForegroundColor Yellow
    $mklinkCmd = $cmdFormats.Mklink -f $MountAddress
    $mklinkPs = $cmdFormats.CmdOverPs -f $mklinkCmd
    Write-Host $messages.CmdCommandPromptAdmin -ForegroundColor Cyan -NoNewLine
    Write-Host $mklinkCmd -ForegroundColor Gray
    Write-Host ("    {0}" -f $messages.Or) -ForegroundColor Cyan
    Write-Host $messages.CmdPowershellAdmin -ForegroundColor Cyan -NoNewLine
    Write-Host $mklinkPs -ForegroundColor Gray
}

function Print-NextSteps()
{
    if ($nextSteps.Count -gt 0)
    {
        Print-HorizontalLine
        Write-Host ($messages.NextStep -f $nextSteps.Count) -ForegroundColor Cyan
    }
    else
    {
        # Write-Host $messages.NoNextStep
        return
    }
    for ($i = 0; $i -lt $nextSteps.Count; $i++)
    {
        Write-Host ("`n{0}. {1}" -f ($i + 1), $nextSteps[$i]) -ForegroundColor Cyan
    }
}

function Invoke-PromptCommand([string]$command, [bool]$ignoreError = $false)
{
    $title = $messages.RunCommand -f $command
    Write-Host $title -ForegroundColor Yellow
    $question = $command
    [string[]]$choices = $messages.Yes, $messages.No
    $decision = $Host.UI.PromptForChoice($title, $question, $choices, 1)
    if ($decision -eq 0)
    {
        $commandForInvokeExpression = $command + ';$?'
        if (-Not (Invoke-Expression $commandForInvokeExpression) -And -Not $ignoreError)
        {
            Write-Host ($messages.RunCommandFailed -f $command) -ForegroundColor Red
            return $false
        }
    }
    else
    {
        Write-Host ($messages.IgnoreCommand -f $command) -ForegroundColor Yellow
        return $false
    }
    return $true
}

function Invoke-NextCommands()
{
    if ($nextSteps.Count -gt 0)
    {
        Print-HorizontalLine
        Write-Host ($messages.NextCommand -f $nextCommands.Count) -ForegroundColor Cyan
    }
    else
    {
        # Write-Host $messages.NoNextCommand
        return
    }
    $executedCount = 0
    for ($i = 0; $i -lt $nextCommands.Count; $i++)
    {
        Write-Host ("`n{0}. {1}" -f ($i + 1), $nextCommands[$i]) -ForegroundColor Cyan
        if (Invoke-PromptCommand $nextCommands[$i])
        {
            $executedCount++
        }
    }
    $skippedCount = $nextCommands.Count - $executedCount
    if ($skippedCount -gt 0)
    {
        Write-Host ($messages.SkipNextCommands -f ($nextCommands.Count, $executedCount, $skippedCount)) -ForegroundColor Yellow
    }
}

function Print-Suggestions([string]$localeChoice)
{
    Write-Host $messages.MountFailSuggestion -ForegroundColor Yellow
    if ($messages.MountFailDoc -ne "")
    {
        Write-Host ""
        if ($localeChoice -eq "zh-CN")
        {
            Write-Host ($messages.MountFailDoc -f $references.AlinasSmbFaq) -ForegroundColor Yellow
        }
        else
        {
            Write-Host ($messages.MountFailDoc -f $references.AlibabaCloudSmbFaq) -ForegroundColor Yellow
        }
    }
}

### Main Script ###
# Registry action required
$global:regeditNeeded = $false
$global:localServiceNeeded = $false
$global:netComponentNeeded = $false
$global:lanmanNotInProviderOrder = $false
# System output encoding
if ($Locale -eq "auto")
{
    $localeChoice = $(Get-UICulture).Name
}
else
{
    $localeChoice = $Locale
}
# Save original system output encoding
$sysEncoding = [System.Console]::OutputEncoding
$cnEncoding = [System.Text.Encoding]::GetEncoding(936)
# Initialize recommended next steps
$nextSteps = [System.Collections.ArrayList]@()
$nextCommands = [System.Collections.ArrayList]@()

# Use chinese encoding in powershell if locale is zh-CN
if ($localeChoice -eq "zh-CN")
{
    try
    {
        [System.Console]::OutputEncoding = $cnEncoding
    }
    catch
    {
        $localeChoice = $(Get-UICulture).Name
        Write-Host "* Failed to load zh-CN encoding. Continue in English..." -ForegroundColor Yellow
    }
}

try
{
    # Get localized messages
    $messages = Get-LocaleMessages $localeChoice
    # Get reference urls
    $references = Get-ReferenceUrls
    # Get commands
    $cmdFormats = Get-CmdFormats

    # Welcome Header
    Print-Header

    # Show suggestions about failed mount
    Print-HorizontalLine
    Print-Suggestions $localeChoice

    Write-Host ""
    Print-HorizontalLine
    # Check Windows system version
    $sysReqPass = Check-SystemRequirement
    if (-Not $sysReqPass)
    {
        Print-NextSteps
        exit 1
    }

    # Check network components
    Check-NetComponent

    # Check local services
    Check-LocalServices

    # Check NFS Client on Windows
    Check-NfsService

    if ($CheckAD)
    {
        Print-HorizontalLine
        $isADController = Check-ADControllerSettings
        if (-Not $isADController)
        {
            Print-HorizontalLine
            $isAdValid = Check-ADClientSettings
        }
    }

    if ($ConfigAD)
    {
        $result = Set-ADControllerSettings
    }

    # Validate mount target
    $hasMountTarget = Check-MountTarget $MountAddress

    # Show next steps if available
    Write-Host ""
    Print-NextSteps

    # Show mount commands if a mount target is valid
    if ($hasMountTarget)
    {
        if ($SystemMount)
        {
            Print-HorizontalLine
            $result = Invoke-SystemMount
        }
        elseif ($InvokeMount)
        {
            Write-Host ""
            Print-HorizontalLine
            Print-MountCommands
            $result = Invoke-MountTarget
        }
    }
    elseif ($SystemMount)
    {
        Write-Host ($messages.SkipSystemMount -f $MountAddress) -ForegroundColor Red
    }
    elseif ($InvokeMount)
    {
        Write-Host ($messages.SkipMount -f $MountAddress) -ForegroundColor Red
    }
}
catch
{
    Write-Host ($messages.PrintException -f $_.ScriptStackTrace, $_.Exception.Message) -ForegroundColor Red

    # Show next steps if available
    Write-Host ""
    Print-NextSteps
}
finally
{
    [System.Console]::Out.Flush()
}

Invoke-NextCommands

# Print footer
Write-Host ""
Print-HorizontalLine
Write-Host ($messages.Question -f $references.AliyunChinaSupport, $references.AlibabaCloudIntlSupport)
Write-Host ""
# Recover system output encoding
$currEncoding = [System.Console]::OutputEncoding
if ($sysEncoding -ne $currEncoding)
{
    Write-Host ($messages.PrintEncodingError -f $currEncoding.EncodingName, $sysEncoding.EncodingName, $sysEncoding.CodePage) -ForegroundColor Yellow
}
Read-Host -Prompt $messages.EnterToExit
