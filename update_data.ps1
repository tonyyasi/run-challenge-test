# San Jose Sharks Running Challenge - Local PowerShell Data Updater
# Can be run directly on Windows: .\update_data.ps1

$ErrorActionPreference = "Stop"
$SHARKS_TEAM_ID = 28
$BASE_URL = "https://api-web.nhle.com/v1"

$pacificTz = [System.TimeZoneInfo]::FindSystemTimeZoneById("Pacific Standard Time")
$pacificNow = [System.TimeZoneInfo]::ConvertTimeFromUtc([System.DateTime]::UtcNow, $pacificTz)
$yesterdayStr = $pacificNow.AddDays(-1).ToString("yyyy-MM-dd")
$todayStr = $pacificNow.ToString("yyyy-MM-dd")

Write-Host "[INFO] Running Sharks workout check (PowerShell)" -ForegroundColor Cyan
Write-Host "       Today: $todayStr | Yesterday: $yesterdayStr"

# Load existing cache if present
$cachedGames = @{}
if (Test-Path "data.json") {
    try {
        $oldData = Get-Content "data.json" -Raw | ConvertFrom-Json
        if ($oldData.games) {
            foreach ($cg in $oldData.games) {
                if ($cg.id -and ($null -ne $cg.totalMiles)) {
                    $cachedGames[[string]$cg.id] = $cg
                }
            }
            Write-Host "[INFO] Loaded $($cachedGames.Count) cached game calculations." -ForegroundColor Gray
        }
    } catch {
        Write-Host "[WARN] Could not parse existing data.json: $_" -ForegroundColor Yellow
    }
}

Write-Host "[INFO] Fetching full Sharks schedule from NHL API..." -ForegroundColor Cyan
$scheduleRes = Invoke-RestMethod -Uri "$BASE_URL/club-schedule-season/SJS/now"
$allGames = $scheduleRes.games

Write-Host "[INFO] Found $($allGames.Count) games in schedule." -ForegroundColor Gray

$processedGames = @()
$totalSeasonMiles = 0.0
$totalGoals = 0
$totalEmptyPP = 0
$totalHatTricks = 0
$wins = 0
$losses = 0
$otLosses = 0

$yesterdayGameObj = $null
$latestCompletedGameObj = $null
$nextGameObj = $null

foreach ($g in $allGames) {
    $gameIdStr = [string]$g.id
    $isHome = $g.homeTeam.id -eq $SHARKS_TEAM_ID
    $sjsData = if ($isHome) { $g.homeTeam } else { $g.awayTeam }
    $oppData = if ($isHome) { $g.awayTeam } else { $g.homeTeam }
    
    $isFinal = ($g.gameState -eq "FINAL" -or $g.gameState -eq "OFF")
    $oppAbbrev = $oppData.abbrev
    $oppName = if ($oppData.commonName.default) { $oppData.commonName.default } else { $oppData.placeName.default }
    
    $gameObj = [ordered]@{
        id = $g.id
        date = $g.gameDate
        startTimeUTC = $g.startTimeUTC
        isHome = $isHome
        oppAbbrev = $oppAbbrev
        oppName = $oppName
        oppLogo = $oppData.logo
        sharksLogo = $sjsData.logo
        gameState = $g.gameState
        gameScheduleState = if ($g.gameScheduleState) { $g.gameScheduleState } else { "OK" }
    }

    if ($isFinal) {
        if ($cachedGames.ContainsKey($gameIdStr) -and ($null -ne $cachedGames[$gameIdStr].totalMiles)) {
            $cached = $cachedGames[$gameIdStr]
            # Copy over calculated properties
            $gameObj["sharksScore"] = $cached.sharksScore
            $gameObj["oppScore"] = $cached.oppScore
            $gameObj["result"] = $cached.result
            $gameObj["gameOutcome"] = $cached.gameOutcome
            $gameObj["goals"] = $cached.goals
            $gameObj["oppPPGoals"] = $cached.oppPPGoals
            $gameObj["oppPPOpps"] = $cached.oppPPOpps
            $gameObj["oppEmptyPP"] = $cached.oppEmptyPP
            $gameObj["oppPPSummary"] = $cached.oppPPSummary
            $gameObj["hatTricks"] = $cached.hatTricks
            $gameObj["hatTrickPlayers"] = $cached.hatTrickPlayers
            $gameObj["goalScorers"] = $cached.goalScorers
            $gameObj["milesBreakdown"] = $cached.milesBreakdown
            $gameObj["totalMiles"] = $cached.totalMiles
        } else {
            $sScore = [int]$sjsData.score
            $oScore = [int]$oppData.score
            $gameObj["sharksScore"] = $sScore
            $gameObj["oppScore"] = $oScore
            
            $won = $sScore -gt $oScore
            $gameObj["result"] = if ($won) { "W" } else { "L" }
            $gameObj["gameOutcome"] = if ($g.gameOutcome.lastPeriodType) { $g.gameOutcome.lastPeriodType } else { "REG" }

            $oppEmptyPP = 0
            $oppPPGoals = 0
            $oppPPOpps = 0
            $hatTricks = 0
            $hatTrickPlayers = @()
            $goalScorers = @()

            try {
                $rr = Invoke-RestMethod -Uri "$BASE_URL/gamecenter/$($g.id)/right-rail"
                $ppStat = $rr.teamGameStats | Where-Object { $_.category -eq "powerPlay" }
                $oppPPStr = if ($isHome) { $ppStat.awayValue } else { $ppStat.homeValue }
                if ($oppPPStr -match "(\d+)/(\d+)") {
                    $oppPPGoals = [int]$Matches[1]
                    $oppPPOpps = [int]$Matches[2]
                    $oppEmptyPP = [Math]::Max(0, $oppPPOpps - $oppPPGoals)
                }
            } catch {}

            try {
                $landing = Invoke-RestMethod -Uri "$BASE_URL/gamecenter/$($g.id)/landing"
                $playerGoalCounts = @{}
                $playerNames = @{}
                if ($landing.summary -and $landing.summary.scoring) {
                    foreach ($period in $landing.summary.scoring) {
                        if ($period.goals) {
                            foreach ($goal in $period.goals) {
                                if ($goal.teamAbbrev.default -eq "SJS") {
                                    $scorerId = [string]$goal.playerId
                                    $scorerName = $goal.name.default
                                    $goalScorers += [ordered]@{
                                        name = $scorerName
                                        period = $period.periodDescriptor.number
                                        time = $goal.timeInPeriod
                                        strength = $goal.strength
                                    }
                                    if (-not $playerGoalCounts.ContainsKey($scorerId)) {
                                        $playerGoalCounts[$scorerId] = 0
                                        $playerNames[$scorerId] = $scorerName
                                    }
                                    $playerGoalCounts[$scorerId]++
                                }
                            }
                        }
                    }
                }
                foreach ($k in $playerGoalCounts.Keys) {
                    if ($playerGoalCounts[$k] -ge 3) {
                        $hatTricks++
                        $hatTrickPlayers += "$($playerNames[$k]) ($($playerGoalCounts[$k]))"
                    }
                }
            } catch {}

            $goalsMiles = [double]($sScore * 1.0)
            $ppMiles = [double]($oppEmptyPP * 0.25)
            $hatTrickMiles = [double]($hatTricks * 2.0)
            $gameMiles = [Math]::Round($goalsMiles + $ppMiles + $hatTrickMiles, 2)

            $gameObj["goals"] = $sScore
            $gameObj["oppPPGoals"] = $oppPPGoals
            $gameObj["oppPPOpps"] = $oppPPOpps
            $gameObj["oppEmptyPP"] = $oppEmptyPP
            $gameObj["oppPPSummary"] = "$oppPPGoals/$oppPPOpps"
            $gameObj["hatTricks"] = $hatTricks
            $gameObj["hatTrickPlayers"] = $hatTrickPlayers
            $gameObj["goalScorers"] = $goalScorers
            $gameObj["milesBreakdown"] = [ordered]@{
                goalsMiles = $goalsMiles
                ppMiles = $ppMiles
                hatTrickMiles = $hatTrickMiles
                totalMiles = $gameMiles
            }
            $gameObj["totalMiles"] = $gameMiles
        }

        # Accumulate totals
        if ($gameObj["result"] -eq "W") {
            $wins++
        } else {
            if ($gameObj["gameOutcome"] -eq "OT" -or $gameObj["gameOutcome"] -eq "SO") {
                $otLosses++
            } else {
                $losses++
            }
        }
        $totalSeasonMiles += [double]$gameObj["totalMiles"]
        $totalGoals += [int]$gameObj["goals"]
        $totalEmptyPP += [int]$gameObj["oppEmptyPP"]
        $totalHatTricks += [int]$gameObj["hatTricks"]

        $latestCompletedGameObj = $gameObj
    } else {
        if ($null -eq $nextGameObj) {
            $nextGameObj = $gameObj
        }
    }

    if ($g.gameDate -eq $yesterdayStr) {
        $yesterdayGameObj = $gameObj
    }

    $processedGames += $gameObj
}

$totalCompleted = $wins + $losses + $otLosses
$avgMiles = if ($totalCompleted -gt 0) { [Math]::Round($totalSeasonMiles / $totalCompleted, 2) } else { 0.0 }

# Backward compatible root attributes
$played = ($null -ne $yesterdayGameObj) -and ($yesterdayGameObj.gameState -eq "FINAL" -or $yesterdayGameObj.gameState -eq "OFF")
$sharksScore = if ($played) { [int]$yesterdayGameObj.sharksScore } else { 0 }
$oppScore = if ($played) { [int]$yesterdayGameObj.oppScore } else { 0 }
$oppName = if ($played) { [string]$yesterdayGameObj.oppAbbrev } else { "" }
$goals = if ($played) { [int]$yesterdayGameObj.goals } else { 0 }
$oppEmptyPP = if ($played) { [int]$yesterdayGameObj.oppEmptyPP } else { 0 }
$hatTricks = if ($played) { [int]$yesterdayGameObj.hatTricks } else { 0 }
$totalMiles = if ($played) { [double]$yesterdayGameObj.totalMiles } else { 0.0 }

$outputObj = [ordered]@{
    date = $yesterdayStr
    played = $played
    sharks_score = $sharksScore
    opp_score = $oppScore
    opp_name = $oppName
    goals = $goals
    pp_goals = $oppEmptyPP
    opp_empty_pp = $oppEmptyPP
    hat_tricks = $hatTricks
    total_miles = [Math]::Round($totalMiles, 2)
    last_updated = $pacificNow.ToString("o")
    today_date = $todayStr
    yesterday_game = $yesterdayGameObj
    latest_completed_game = $latestCompletedGameObj
    next_game = $nextGameObj
    season_summary = [ordered]@{
        total_miles = [Math]::Round($totalSeasonMiles, 2)
        games_played = $totalCompleted
        record = "$wins-$losses-$otLosses"
        wins = $wins
        losses = $losses
        ot_losses = $otLosses
        total_goals = $totalGoals
        total_empty_pp = $totalEmptyPP
        total_hat_tricks = $totalHatTricks
        avg_miles_per_game = $avgMiles
    }
    games = $processedGames
}

Write-Host "[INFO] Saving updated data to data.json and data.js..." -ForegroundColor Cyan
$jsonStr = $outputObj | ConvertTo-Json -Depth 10
Set-Content -Path "data.json" -Value $jsonStr -Encoding UTF8
Set-Content -Path "data.js" -Value "window.SHARKS_DATA = $jsonStr;" -Encoding UTF8

Write-Host "[SUCCESS] Generated data.json and data.js with $($processedGames.Count) games. Season Total: $totalSeasonMiles miles" -ForegroundColor Green
