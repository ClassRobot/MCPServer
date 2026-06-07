param(
    [string]$ImageName = "mcp-server:prod",
    [string]$ContainerName = "mcp-server",
    [int]$HostPort = 8000,
    [string]$DataVolume = "mcp-server-data",
    [string]$AptDebianMirror = "",
    [string]$AptDebianSecurityMirror = ""
)

$ErrorActionPreference = "Stop"

$dockerInfo = docker info 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not available. Please start Docker Desktop and retry."
}

$proxyLines = $dockerInfo | Where-Object { $_ -match "HTTP Proxy|HTTPS Proxy" }
if ($proxyLines -match "127\.0\.0\.1:1080") {
    Write-Warning "Docker Desktop is configured to use 127.0.0.1:1080 as proxy. If that proxy is not running, apt/Playwright downloads will fail."
    Write-Warning "Fix it in Docker Desktop Settings > Resources > Proxies, or start the local proxy before running this script."
}

$buildArgs = @("build", "-t", $ImageName)
if ($AptDebianMirror) {
    $buildArgs += @("--build-arg", "APT_DEBIAN_MIRROR=$AptDebianMirror")
}
if ($AptDebianSecurityMirror) {
    $buildArgs += @("--build-arg", "APT_DEBIAN_SECURITY_MIRROR=$AptDebianSecurityMirror")
}
$buildArgs += "."

docker @buildArgs

$existing = docker ps -aq --filter "name=^/$ContainerName$"
if ($existing) {
    docker rm -f $ContainerName | Out-Null
}

docker run -d `
    --name $ContainerName `
    -p "${HostPort}:8000" `
    -v "${DataVolume}:/data" `
    -e MCP_MARKITDOWN_ALLOWED_ROOTS="/app:/data" `
    -e MCP_MARKITDOWN_OUTPUT_DIR="/data/markitdown" `
    $ImageName

docker ps --filter "name=^/$ContainerName$"
