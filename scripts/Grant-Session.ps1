# RC5.1: legacy interactive script intentionally retired.
# Typing AUTORIZAR into a script is not independent proof of physical presence:
# a previously authorized remote shell can automate stdin.
[CmdletBinding()]
param(
    [ValidateSet('writes','shell','screen','input')]
    [string[]]$Capabilities = @(),
    [ValidateRange(1,60)]
    [int]$Minutes = 15
)
$ErrorActionPreference = 'Stop'
throw 'RC5.1 security policy: granting via the legacy script is disabled. Open the LOCAL Universal Remote application, Acesso > select capabilities > Autorizar. No permission was granted.'
