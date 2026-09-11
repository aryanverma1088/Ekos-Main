---
doc_key: eng-incident-response-sop
title: Incident Response SOP
department: Engineering
doc_type: SOP
version: "2.0"
created_date: 2023-09-15
effective_date: 2023-10-01
updated_date: 2024-06-01
author: Marcus Webb
owner: Engineering
authority_level: 2
status: current
supersedes: null
tags: incident-response, on-call, engineering
---

# Incident Response SOP

## Purpose

This SOP describes how Engineering responds to production incidents,
from detection through resolution and review.

## Severity Levels

Incidents are classified as SEV-1 (full outage), SEV-2 (partial
degradation), or SEV-3 (minor issue with workaround available).

## Escalation Process

The on-call engineer must acknowledge a page within 10 minutes. If a
SEV-1 incident is not mitigated within 30 minutes, it is automatically
escalated to the engineering manager and, for customer-facing outages,
to the Head of Engineering.

## Incident Channel

Every incident gets a dedicated channel named `#incident-<id>` where
all communication and timeline updates are logged.

## Postmortems

A blameless postmortem is required for all SEV-1 and SEV-2 incidents
within 5 business days of resolution, documenting root cause and
follow-up action items.

## Communication

Customer-facing status updates during incidents are coordinated with
the support team via the status page.
