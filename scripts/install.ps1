param(
    [switch]$DryRun,
    [ValidateSet('user', 'project')]
    [string]$Scope = 'user',
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
$arguments = @('-m', 'skill_gate', 'install', '--scope', $Scope, '--project-root', $ProjectRoot)
if ($DryRun) { $arguments += '--dry-run' }
python @arguments
