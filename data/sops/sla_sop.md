# SLA Tracking SOP
Version: 2.0
Last updated: 2026-02-03

## Purpose
To ensure SLA compliance is tracked accurately across all support tickets and reported weekly.

## Target Team
CX Operations

## Related Teams
CX Support Agents, Engineering, Finance

## Steps

### Step 1 -- SLA Clock Start
The SLA clock starts at the moment a ticket is created in Zendesk. This applies to all inbound tickets regardless of source.

### Step 2 -- SLA Thresholds
Monitor the following SLA thresholds:
- P1: First response within 1 hour, resolution within 4 hours
- P2: First response within 4 hours, resolution within 24 hours
- P3: First response within 8 hours, resolution within 72 hours

### Step 3 -- Breach Alerts
Zendesk triggers an automatic Slack alert to #sla-alerts when a ticket is within 30 minutes of breaching its first response SLA. The assigned agent must acknowledge the alert within 10 minutes.

### Step 4 -- SLA Reporting
Export the SLA compliance report from Zendesk every Monday at 9am. Share in #cx-ops-weekly with a summary of breach rate by priority level.

### Step 5 -- Breach Review
Any SLA breach must be logged in the breach tracker (Notion: CX Ops > SLA Breaches). Include ticket ID, breach reason, and corrective action taken.
