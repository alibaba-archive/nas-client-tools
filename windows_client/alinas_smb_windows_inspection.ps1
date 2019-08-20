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
    Run alinas_smb_windows_inspection powershell script to detect:
     1. The NAS (SMB protocol) compatibility of the local computer
     2. Server roles and features that might affect the performance of NAS (SMB protocol)
     3. Connection problems regarding the provided mount target address

    Usage example:
      .\alinas_smb_windows_inspection.ps1 -MountAddress abcde-123.region-id.nas.aliyuncs.com -Locale zh-CN
#>

param (
    # Specify the mount target address to test in the format of "<MOUNT_TARGET_ID>.<REGION_ID>.nas.aliyuncs.com"
    [string]$MountAddress = "",
    # Default is "auto", put "zh-CN" to output messages in Chinese
    [string]$Locale = "auto"
)

function Get-ReferenceUrls()
{
    $urls = @{
        AlinasSmbFaq = "https://help.aliyun.com/knowledge_list/110787.html";
        AlibabaCloudSmbFaq = "https://www.alibabacloud.com/help/faq-list/110787.htm";
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
        CheckMountTarget = "Check mount target: {0}";
        # Next step strings
        NextStep = "The following {0} action(s) are recommended:";
        NoNextStep = "No suggested actions at this point.";
        NsSysReqNotMet = "Access NAS (SMB protocol) from {0} ({1}) or newer systems";
        NsNoGuestAccess = "Guest auth is required to access SMB NAS, please configure the Registry value: `n{0}`n   See Microsoft support document for details:`n     {1}";
        NsServiceNotRunning = "Key local services not running. Please search and run `"services.msc`", then start the following service(s):`n{0}";
        NsServiceNotRunningTpl = "   - Service: {0}";
        NsHasNfsService = "The installed NFS services may affect the performance of SMB NAS. If you do not need NFS service, please consider:`n{0}";
        NsHasNfsService1 = "   - Remove '{0}' role from the system";
        NsHasNfsService2 = "   - Delete Nfsnp from the Registry entry:`n{0}";
        NsCorrectMountTarget = "Please provide correct mount target address (format: {0})";
        NsBadConnection = "Failed to ping {0}, possible reasons are:`n   - mount target address typo`n   - client and mount target are not in the same VPC`n   - something is wrong with inter-VPC or VPN connection`n   - something is wrong with DNS service";
        NsBadSmbConnection1 = "NAS service is not available via mount target ({0}), please double-check mount point address";
        # Mount suggestions
        MountFailSuggestion = "* Note: common reasons for SMB NAS share mount failures are:`n   1) network connectivity`n   2) unsupported client system version or settings`n   3) try to mount a NFS NAS as an SMB NAS`n   4) inproper NAS permission group settings`n   5) an overdue account";
        MountFailDoc = "  View detailed solutions in official documentation:`n   {0}";
        # Mount instructions
        FixGuestAccessFirst = "* Before running the following mount commands, please follow recommended action to allow guest access to SMB";
        FixLocalServices = "* Before running the following mount commands, please follow recommended action to start key local services via services.msc";
        MountRef = "Please refer to the following example commands to mount your SMB NAS volume:";
        MountRefNetUse = " - Mount SMB NAS file system to a volume label (Z: in the example command):";
        MountRefMklink = " - Mount SMB NAS file system as a sub-directory (symbolic link to C:\myshare in the example command):";
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
        SysReqNotMet = "阿里云文件存储 NAS SMB 协议要求客户端运行{0} ({1})或更新版本的操作系统";
        CurrSys = "当前系统版本: {0} ({1})";
        CheckServices = "检查相关系统本地服务";
        CheckRoles = "检查相关系统角色与服务";
        CheckMountTarget = "检查挂载点: {0}";
        # Next step strings
        NextStep = "推荐进行以下{0}个操作:";
        NoNextStep = "暂时没有推荐的下一步操作。";
        NsSysReqNotMet = "使用{0} ({1})或更新版本的操作系统访问 SMB 协议 NAS";
        NsNoGuestAccess = "需要系统允许通过 Guest 身份访问 NAS，请修改注册表项: `n{0}`n   详见微软官方支持文档:`n     {1}";
        NsServiceNotRunning = "关键系统本地服务并未启动，请搜索并运行`"services.msc`"，然后启动以下服务:`n{0}";
        NsServiceNotRunningTpl = "   - 服务: {0}";
        NsHasNfsService = "系统中已安装的 NFS 相关服务可能影响 SMB 协议 NAS 的性能。如果您并不需要 NFS 服务，请考虑:`n{0}";
        NsHasNfsService1 = "   - 从服务器角色中移除'{0}'";
        NsHasNfsService2 = "   - 在以下注册表项中删除 Nfsnp:`n{0}";
        NsCorrectMountTarget = "请提供正确格式的挂载点地址 (格式: {0})";
        NsBadConnection = "Ping 挂载点失败 ({0})，请检查下列可能的问题:`n   - 挂载点地址拼写错误`n   - 客户端与挂载点不在同一个 VPC`n   - 跨 VPC 连接或 VPN 连接存在问题`n   - DNS 服务故障，请检查配置";
        NsBadConnection1 = "挂载点未发现 NAS 服务 ({0})，请检查挂载点地址";
        # Mount suggestions
        MountFailSuggestion = "* 提示: SMB NAS挂载失败的常见原因为:`n   1) 网络不通`n   2) 客户端系统版本或设置问题`n   3) 错以SMB NAS挂载方式挂载NFS NAS`n   4) NAS权限组设置问题`n   5) NAS服务欠费";
        MountFailDoc = "  详见相关官方文档: {0}";
        # Mount instructions
        FixGuestAccessFirst = "* 运行以下命令之前，请先按推荐操作修改注册表以允许通过 Guest 身份访问 NAS";
        FixLocalServices = "* 运行以下命令之前，请先按推荐操作启动关键系统本地服务";
        MountRef = "请参考以下命令挂载 SMB 协议 NAS 文件系统:";
        MountRefNetUse = " - 挂载 SMB NAS 文件系统到盘符 (命令范例中为 Z:):";
        MountRefMklink = " - 挂载 SMB NAS 文件系统到子目录 (命令范例中为指向 C:\myshare 的符号链接):";
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
            if ($allowGuest -eq $null)
            {
                $value = "null"
            }
            else
            {
                $value = "$allowGuest"
            }
            $failMsg = $messages.Fail -f ("[{0}] {1}: {2}" -f $registryPath, $registryName, $value)
            Write-Host $failMsg -ForegroundColor Red
            Add-NextStep ($messages.NsNoGuestAccess -f ("    [{0}]`n    {1}=REG_DWORD:1" -f $registryPath, $registryName), $references.MsftSmbGuestAccess)
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
    try {
        $ip = [System.Net.Dns]::GetHostAddresses($computerName) | select-object IPAddressToString -ExpandProperty  IPAddressToString
        if($ip.GetType().Name -eq "Object[]")
        {
            $ip = $ip[0]
        }
    } catch {
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
    Add-NextStep ($messages.NsBadConnection1 -f $MountAddress)
    Write-Host $failMsg -ForegroundColor Red
    return $false
}

function Check-NfsService()
{
    $actionString = ""

    Import-Module ServerManager

    # Check FS-NFS-Service* role
    $nfsServices = Get-WindowsFeature FS-NFS-Service*
    if ($nfsServices.Count -gt 0 -And $nfsServices[0].Installed)
    {
        $actionString = $messages.NsHasNfsService1 -f $nfsServices[0].DisplayName
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
            [void]$servicesToStart.Add($localService.DisplayName)
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
        }
        $failMsg = $messages.Fail -f $messages.CheckServices
        Write-Host $failMsg -ForegroundColor Red
        Add-NextStep ($messages.NsServiceNotRunning -f $actionString)
        $global:localServiceNeeded = $true
    }
    else
    {
        $passMsg = $messages.Pass -f $messages.CheckServices
        Write-Host $passMsg -ForegroundColor Green
    }
}

function Print-Header()
{
    Write-Host ("`n=== {0} ===" -f $messages.Header)
    if ($MountAddress -eq "")
    {
        Write-Host ($messages.MissingMountTarget -f $messages.MountTargetTpl) -ForegroundColor Yellow
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

    # Check local services
    Check-LocalServices

    # Check NFS Client on Windows
    Check-NfsService

    # Validate mount target
    $hasMountTarget = Check-MountTarget $MountAddress

    # Show next steps if available
    Write-Host ""
    Print-NextSteps

    # Show mount commands if a mount target is valid
    if ($hasMountTarget)
    {
        Write-Host ""
        Print-HorizontalLine
        Print-MountCommands
    }
}
catch
{
    Write-Host "An error occurred:" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    Write-Host "Exception:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red

    # Show next steps if available
    Write-Host ""
    Print-NextSteps
}
finally
{
    [System.Console]::Out.Flush()
    # Print footer
    Write-Host ""
    Write-Host ($messages.Question -f $references.AliyunChinaSupport, $references.AlibabaCloudIntlSupport)
    Write-Host ""
    # Recover system output encoding
    $currEncoding = [System.Console]::OutputEncoding
    if ($sysEncoding -ne $currEncoding)
    {
        Write-Host "`n!! NOTICE: console output encoding has been changed to $($currEncoding.EncodingName)"
        Write-Host "- Run the following command to recover original console output encoding ($($sysEncoding.EncodingName)):"
        Write-Host "  [System.Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding($($sysEncoding.CodePage))"
    }

    Read-Host -Prompt $messages.EnterToExit
}
