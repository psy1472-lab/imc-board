# IMC 전용 Supabase 프로젝트 생성 + 스키마 적용 + (선택) 데이터 마이그레이션
# Usage:
#   .\scripts\setup_imc_supabase.ps1 -AccessToken "sbp_..."
#   .\scripts\setup_imc_supabase.ps1 -AccessToken "sbp_..." -SkipDataMigration

param(
    [Parameter(Mandatory = $true)]
    [string]$AccessToken,

    [string]$ProjectName = "imc-operations-dashboard",
    [string]$Region = "ap-northeast-2",
    [string]$DbPassword = "",
    [switch]$SkipDataMigration,
    [switch]$SkipRailway
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

if (-not $DbPassword) {
    $chars = (48..57) + (65..90) + (97..122)
    $DbPassword = -join ($chars | Get-Random -Count 24 | ForEach-Object { [char]$_ })
}

Write-Step "Supabase CLI login"
npx supabase login --token $AccessToken | Out-Null

Write-Step "Organization 조회"
$orgsJson = npx supabase orgs list -o json 2>&1 | Out-String
$orgs = $orgsJson | ConvertFrom-Json
if (-not $orgs -or $orgs.Count -eq 0) {
    throw "Supabase organization not found"
}
$orgId = $orgs[0].id
Write-Host "Using org: $($orgs[0].name) ($orgId)"

Write-Step "프로젝트 생성: $ProjectName (region=$Region)"
$createJson = npx supabase projects create $ProjectName --org-id $orgId --db-password $DbPassword --region $Region -o json 2>&1 | Out-String
$created = $createJson | ConvertFrom-Json
$projectRef = $created.id
if (-not $projectRef) {
    throw "Project creation failed: $createJson"
}
Write-Host "Project ref: $projectRef"

Write-Step "프로젝트 provisioning 대기 (최대 3분)"
$ready = $false
for ($i = 0; $i -lt 36; $i++) {
    Start-Sleep -Seconds 5
    $listJson = npx supabase projects list -o json 2>&1 | Out-String
    $projects = $listJson | ConvertFrom-Json
    $proj = $projects | Where-Object { $_.id -eq $projectRef -or $_.ref -eq $projectRef }
    if ($proj -and $proj.status -eq "ACTIVE_HEALTHY") {
        $ready = $true
        break
    }
    Write-Host "  waiting... ($($i + 1)/36)"
}
if (-not $ready) {
    Write-Warning "Project may still be provisioning. Continue manually if db push fails."
}

Write-Step "supabase link"
npx supabase link --project-ref $projectRef --password $DbPassword --yes 2>&1 | Out-Null

Write-Step "IMC 스키마 migration 적용 (db push)"
npx supabase db push --password $DbPassword --yes

$databaseUrl = "postgresql://postgres.$projectRef`:$DbPassword@aws-0-$Region.pooler.supabase.com:5432/postgres"
$envFile = Join-Path $Root ".env.supabase.local"
@"
# IMC dedicated Supabase (generated $(Get-Date -Format 'yyyy-MM-dd HH:mm'))
SUPABASE_PROJECT_REF=$projectRef
SUPABASE_PROJECT_NAME=$ProjectName
SUPABASE_DB_PASSWORD=$DbPassword
DATABASE_URL=$databaseUrl
SUPABASE_URL=https://$projectRef.supabase.co
"@ | Set-Content -Path $envFile -Encoding UTF8
Write-Host "Saved credentials to .env.supabase.local (gitignored via .env.local pattern)"

if (-not $SkipDataMigration -and (Test-Path "data/imc_dashboard.db")) {
    Write-Step "SQLite -> Postgres 데이터 마이그레이션"
    pip install "psycopg[binary]" -q
    $env:DATABASE_URL = $databaseUrl
    python backend/scripts/migrate_sqlite_to_postgres.py --sqlite "data/imc_dashboard.db"
    if ($LASTEXITCODE -ne 0) { throw "Data migration failed" }
}

if (-not $SkipRailway) {
    Write-Step "Railway DATABASE_URL 업데이트"
    railway variables --set "DATABASE_URL=$databaseUrl" 2>&1 | Out-Null
    railway redeploy 2>&1 | Out-Null
    Write-Host "Railway redeploy triggered"
}

Write-Step "완료"
Write-Host @"

IMC 전용 Supabase 프로젝트가 생성되었습니다.

  Dashboard : https://supabase.com/dashboard/project/$projectRef
  Project   : $ProjectName
  Ref       : $projectRef
  Region    : $Region

다음 단계:
  1. Cursor Supabase MCP를 새 프로젝트($projectRef)로 재연결
  2. GET /api/health 에서 database=postgres 확인
  3. .env.supabase.local 의 DATABASE_URL을 Railway에 반영됐는지 확인

"@
