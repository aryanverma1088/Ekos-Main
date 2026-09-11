---
doc_key: eng-deployment-policy
title: Deployment Policy
department: Engineering
doc_type: SOP
version: "1.0"
created_date: 2023-05-01
effective_date: 2023-06-01
updated_date: 2023-05-01
author: Marcus Webb
owner: Engineering
authority_level: 2
status: current
supersedes: null
tags: deployment, ci-cd, engineering
---

# Deployment Policy

## Purpose

This policy describes the standard process for deploying code changes
to production at Aurelia Technologies.

## Ownership

The **Platform team owns the production deployment process**,
including the CI/CD pipeline, rollout tooling, and rollback
procedures. Feature teams are responsible for the correctness of their
own code but rely on Platform-owned tooling to ship it.

## Deployment Windows

Standard deployments occur during business hours, Monday through
Thursday. Friday deployments require sign-off from the Platform team
lead due to reduced on-call coverage over the weekend.

## Rollback Procedure

Any deployment causing a SEV-1 or SEV-2 incident must be rolled back
immediately using the automated rollback tool, coordinated with the
on-call engineer.

## Code Review Requirement

All changes deployed to production must have at least one approving
code review, per the Code Review Guidelines.
