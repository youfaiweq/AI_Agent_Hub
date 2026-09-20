$ErrorActionPreference = 'Stop'

$trackedSensitive = @(git ls-files | Where-Object {
    $_ -match '(^|[\\/])\.env$|\.pem$|\.key$|\.p12$|\.pfx$|(^|[\\/])uploads?([\\/]|$)|(^|[\\/])secrets?([\\/]|$)'
})
if ($trackedSensitive.Count -gt 0) {
    Write-Error "Sensitive paths are tracked: $($trackedSensitive -join ', ')"
}

$assignmentHits = @(rg --hidden --glob '!.git/**' --glob '!node_modules/**' --glob '!frontend/dist/**' `
    --glob '!*.example' --glob '!*.md' --glob '!.env' --glob '!.env.*' --glob '!**/tests/**' `
    '(?i)(api[_-]?key|secret[_-]?key|password|jwt[_-]?secret)\s*[:=]\s*["'']?[A-Za-z0-9_-]{20,}' . 2>$null)
if ($assignmentHits.Count -gt 0) {
    Write-Error 'Potential secret assignments found outside example/configuration docs.'
}

git diff --check
Write-Output 'Security audit checks passed: tracked sensitive paths, secret assignments, and whitespace.'
