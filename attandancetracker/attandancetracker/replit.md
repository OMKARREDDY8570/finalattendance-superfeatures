# MITS Realtime Attendance Tracker

A Flask web application that tracks student attendance for Madanapalle Institute of Technology & Science (MITS). It scrapes the official MITS SIMS portal and provides attendance analysis with skip/attend recommendations to help students maintain the 75% threshold.

## Project Structure

- `telegrambot.py` - Main Flask application (single-file project)

## Tech Stack

- **Language**: Python 3.12
- **Framework**: Flask
- **HTTP client**: requests
- **Production server**: gunicorn

## Running the App

The app runs on port 5000:

```
python telegrambot.py
```

## How It Works

1. Student enters their roll number and password
2. The app logs into `mitsims.in` via API
3. Fetches attendance data and parses the response
4. Calculates per-subject attendance percentages
5. Displays an analysis showing which classes can be skipped and which must be attended to stay above 75%

## Deployment

Configured for autoscale deployment using gunicorn:
```
gunicorn --bind=0.0.0.0:5000 --reuse-port telegrambot:app
```
