"""Render aggregate profile contributions from GitHub's contribution calendar."""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen


def streaks(days):
    longest = current = 0
    previous = None
    for day in days:
        when = date.fromisoformat(day["date"])
        if previous is not None and when != previous + timedelta(days=1):
            current = 0
        current = current + 1 if day["contributionCount"] else 0
        longest = max(longest, current)
        previous = when
    # An unfinished day does not end yesterday's streak.
    if days and not days[-1]["contributionCount"]:
        current = 0
        for day in reversed(days[:-1]):
            if not day["contributionCount"]:
                break
            current += 1
    return current, longest


def main():
    login = os.environ["GITHUB_REPOSITORY_OWNER"]
    query = """query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": login}}).encode(),
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Content-Type": "application/json", "User-Agent": "profile-stats"},
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError("GitHub contribution query failed")
    calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    today = datetime.now(timezone.utc).date().isoformat()
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]
            if day["date"] <= today]
    assert days, "GitHub returned an empty contribution calendar"
    assert sum(day["contributionCount"] for day in days) == calendar["totalContributions"]
    current, longest = streaks(days)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    metrics = [("Contributions", f'{calendar["totalContributions"]:,}'),
               ("Current streak", str(current)), ("Longest streak", str(longest))]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="880" height="210" viewBox="0 0 880 210" role="img">',
           '<title>GitHub contribution activity over the past year</title>',
           '<rect width="880" height="210" rx="12" fill="#0d1117"/>',
           '<g font-family="Arial,sans-serif" text-anchor="middle">',
           f'<text x="440" y="30" fill="#00ffb3" font-size="17">{escape(login)} · contribution calendar · past year</text>']
    for x, (label, value) in zip((150, 440, 730), metrics):
        svg += [f'<text x="{x}" y="92" fill="#00ffb3" font-size="38" font-weight="bold">{value}</text>',
                f'<text x="{x}" y="125" fill="#ffffff" font-size="17">{label}</text>']
    svg += [f'<text x="440" y="164" fill="#8b949e" font-size="13">{days[0]["date"]} to {days[-1]["date"]} · streaks in days</text>',
            f'<text x="440" y="188" fill="#8b949e" font-size="12">Updated {updated} · refreshed every 15 minutes from GitHub</text>', '</g></svg>']
    Path("assets/contributions.svg").write_text("\n".join(svg), encoding="utf-8")
    print(f'Contribution calendar: {calendar["totalContributions"]} contributions; updated {updated}')


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        def sample(counts):
            return [{"date": (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
                     "contributionCount": count} for i, count in enumerate(counts)]
        for counts, expected in [([], (0, 0)), ([0, 0], (0, 0)), ([1, 2, 3], (3, 3)),
                                 ([1, 2, 0], (2, 2)), ([2, 0, 0], (0, 1)),
                                 ([1, 1, 0, 1], (1, 2))]:
            assert streaks(sample(counts)) == expected
        print("Contribution streak checks passed")
    else:
        main()
