# 🦈 San Jose Sharks Running Challenge

A web application and automated tracker that turns the results of **San Jose Sharks** hockey games into your daily running mileage goal!

---

## 🏃 Mileage Calculation Rules

The morning after every San Jose Sharks game, your running distance is calculated using the following math:

| Event | Mileage Rule | Description |
| :--- | :---: | :--- |
| **Sharks Goal** | **+1.00 mi** | 1 mile for every goal scored by the Sharks. |
| **Opponent Failed Power Play** | **+0.25 mi** | 0.25 miles each time the opponent has a power play opportunity and does **not** score (successful penalty kill). |
| **Sharks Hat Trick** | **+2.00 mi** | 2 bonus miles each time a Sharks player scores 3 or more goals in a game. |
| **No Game (Rest Day)** | **0.00 mi** | Rest and recovery day! |

$$\text{Total Miles} = (\text{Sharks Goals} \times 1.0) + ((\text{Opponent PP Opportunities} - \text{Opponent PP Goals}) \times 0.25) + (\text{Sharks Hat Tricks} \times 2.0)$$

---

## ✨ Features

- 🏃 **Today's Workout Card**: Tells you immediately how many miles you need to run today, with a full mathematical breakdown and list of goal scorers. If yesterday was a rest day, it displays your recovery status and upcoming game countdown.
- 📅 **Interactive Calendar**: Full month-by-month calendar view with game matchups, scores, win/loss indicators, and running distances directly on each calendar date. Click any game to view its detailed boxscore and mileage calculation.
- 📋 **Results & Schedule Table**: Filter through completed results and upcoming fixtures. Inspect exact power play efficiency, goal counts, and total miles.
- 📊 **Season KPI Tracker**: Tracks season total miles run, Sharks win-loss-OT record, average miles per game, penalty kills defended, and hat tricks.
- 🤖 **Automated Daily Sync**: GitHub Actions runs automatically every morning, pulls game stats from the official NHL API, updates `data.json`, and deploys the new workout.

---

## 🚀 Running Locally

### Option 1: PowerShell (Windows)
No Python installation required!
```powershell
powershell -ExecutionPolicy Bypass -File .\update_data.ps1
```

### Option 2: Python
```bash
pip install requests
python sharks_runner.py
```

### Viewing the App
Open `index.html` in your web browser (or serve it using any local static web server):
```bash
# If using Python:
python -m http.server 8000

# Or simply double-click index.html in File Explorer!
```

---

## ⚙️ Automated GitHub Action

A GitHub Action is configured in [`.github/workflows/daily_run.yml`](.github/workflows/daily_run.yml) to run daily at `15:00 UTC` (morning Pacific Time) and can also be triggered manually anytime via GitHub's **Run workflow** button.
