$ErrorActionPreference = 'Stop'
$baseUrl = if ($env:AGENTHUB_BASE_URL) { $env:AGENTHUB_BASE_URL } else { 'http://127.0.0.1:8000' }

function Assert-Status($label, $scriptBlock, $expected) {
    try {
        & $scriptBlock | Out-Null
        throw "$label returned 2xx unexpectedly"
    } catch {
        if ($null -eq $_.Exception.Response) { throw }
        $status = $_.Exception.Response.StatusCode.value__
        if ($status -ne $expected) { throw "$label returned $status, expected $expected" }
        Write-Output "PASS $label -> HTTP $status"
    }
}

Assert-Status 'invalid token' {
    Invoke-WebRequest "$baseUrl/api/v1/auth/me" -Headers @{ Authorization = 'Bearer invalid-token' }
} 401

Assert-Status 'invalid registration payload' {
    Invoke-WebRequest "$baseUrl/api/v1/auth/register" -Method Post -ContentType 'application/json' -Body '{"email":"not-an-email","password":"short"}'
} 422

$health = Invoke-RestMethod "$baseUrl/health"
if ($health.status -notin @('healthy', 'degraded')) { throw 'Health endpoint returned an invalid status.' }
Write-Output "PASS health endpoint -> $($health.status)"
