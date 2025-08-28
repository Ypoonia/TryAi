# Store Monitoring System

Backend API system for monitoring restaurant store uptime/downtime during business hours.

## Problem Statement

Loop monitors several restaurants in the US and needs to monitor if stores are online or not. All restaurants are supposed to be online during their business hours. Due to some unknown reasons, a store might go inactive for a few hours. Restaurant owners want to get a report of how often this happened in the past.

## Features

- Monitor store status (active/inactive) based on hourly polling data
- Calculate uptime and downtime within business hours only
- Handle different timezones for store locations
- Generate reports for last hour, day, and week
- Asynchronous report generation with status tracking

## API Endpoints

- `POST /trigger_report` - Trigger report generation
- `GET /get_report?report_id=<id>` - Get report status or download CSV

## Data Sources

1. Store status polling data (CSV)
2. Business hours data (CSV) 
3. Store timezone data (CSV)

## Setup

Coming soon...
