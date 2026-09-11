---
doc_key: it-incident-response-policy
title: IT Security Incident Response Policy
department: IT-Security
doc_type: Policy
version: "1.0"
created_date: 2023-08-15
effective_date: 2023-09-01
updated_date: 2024-03-01
author: Daniel Ochieng
owner: IT-Security
authority_level: 1
status: current
supersedes: null
tags: security, incident-response, breach
---

# IT Security Incident Response Policy

## Purpose

This policy defines how Aurelia Technologies detects, responds to, and
recovers from information security incidents, including data breaches,
malware infections, unauthorized access, and denial-of-service events.
It applies to all employees, contractors, and systems connected to the
company network.

## Incident Classification

Security incidents are classified into three tiers. Tier 1 incidents
involve confirmed or suspected exposure of customer or employee personal
data. Tier 2 incidents involve compromise of internal systems without
confirmed data exposure, such as malware on an employee laptop. Tier 3
incidents are minor policy violations or false positives that require
investigation but pose limited immediate risk.

## Detection and Reporting

Any employee who suspects a security incident must report it to the IT
Security team within one hour of discovery, using the internal incident
channel or the emergency security hotline outside business hours.
Automated monitoring systems generate alerts that are triaged by the
on-call security analyst.

## Response Process

Upon confirmation of a Tier 1 or Tier 2 incident, the IT Security team
convenes an incident response group including a security lead, the
relevant system owner, and a representative from Legal for Tier 1
incidents. The group is responsible for containment, eradication of the
threat, and recovery of affected systems.

## Containment

Containment actions may include isolating affected systems from the
network, disabling compromised accounts, and revoking credentials or
access tokens suspected of being compromised. These actions are taken
as quickly as possible to limit the scope of the incident, even before
the full extent of the incident is understood.

## Communication

For Tier 1 incidents involving customer data, Legal and executive
leadership determine whether external notification is required under
applicable regulations, and coordinate any customer or regulator
communication. Internal stakeholders are kept informed via the incident
channel throughout the response.

## Post-Incident Review

Every Tier 1 and Tier 2 incident requires a post-incident review within
10 business days of resolution, documenting the root cause, response
timeline, and any policy or tooling changes needed to prevent
recurrence. This is distinct from the SEV-1/SEV-2 postmortem process
used for production engineering outages, which is described in the
Engineering Incident Response SOP.

## Relationship to Other Policies

This policy works alongside the IT Security Policy and Access Control
Policy. Where a security incident involves a production system, the
Engineering Incident Response SOP also applies for the operational
response, while this policy governs the security-specific response.
