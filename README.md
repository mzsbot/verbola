# Ver Bola ⚽🏎️

A clean, lightning-fast, and ad-free sports schedule aggregator. 
Live at: [verbola.casa](https://verbola.casa)

## 📌 Overview
Ver Bola is a serverless web application designed to provide a frictionless experience for tracking daily Football matches and Formula 1 sessions. Built with a focus on absolute minimalism, the platform aggregates broadcast schedules, converts them to the local Portuguese timezone (Lisbon), and displays them in an optimized, mobile-first grid.

## ⚙️ Technical Architecture
The project operates on a 100% serverless infrastructure, utilizing GitHub as both the execution environment and the hosting provider.

* **Backend / Automation:** A Python scraper (`BeautifulSoup4`, `requests`) runs autonomously every 6 hours via **GitHub Actions**. It parses dynamic HTML from sports directories and queries official F1 public JSON repositories.
* **Data Layer:** Extracted data is sanitized, chronologically sorted, and exported as a static `jogos.json` file directly into the repository.
* **Frontend:** A lightweight, single-page application built with raw HTML/JS and **Tailwind CSS**. It fetches the JSON asynchronously and uses client-side logic to highlight live events dynamically without constant server polling.
* **Hosting:** Served globally via **GitHub Pages** with enforced HTTPS on a custom domain.

## ✨ Key Features
* **Zero-Friction UI:** No ads, no pop-ups, no navigation menus. Just the data.
* **Smart Timezone Management:** Automatically handles UTC to Europe/Lisbon conversions, including daylight saving time rules.
* **Live Event Detection:** Client-side mathematical evaluation cross-references the user's system clock with event durations (115 mins for Football, 120 mins for F1) to trigger real-time "LIVE" visual states.
* **Multi-Sport Integration:** Seamlessly merges distinct data sources (Football leagues + F1 Weekend Sessions) into a single chronological timeline.

---

## ⚖️ Legal Disclaimer & Fair Use

This repository and the resulting web application are strictly for **educational and non-commercial/non-profit purposes**. 

* **No Piracy or Streaming:** This project **does not** host, distribute, or link to any illegal video streams or copyrighted media. It is solely a schedule aggregator (a TV guide).
* **Factual Data:** The data aggregated (match times, team names, television channels) constitutes basic historical/future facts. Under international copyright law, raw facts are not subject to copyright protection.
* **Fair Use:** The automated extraction of schedule data is conducted at highly restrictive intervals (4 times per day) to ensure absolutely zero impact on the source servers' bandwidth or infrastructure. 
* **No Affiliation:** This project is independent and is not affiliated with, endorsed by, or sponsored by *OndeBola*, *F1Calendar*, *Formula 1*, or any sports broadcaster mentioned in the schedules. All trademarks and logos (such as national flags) belong to their respective owners.

If you are a rights holder and have concerns about the aggregation of your public factual schedules, please open an issue in this repository.
