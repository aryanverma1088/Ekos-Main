---
doc_key: eng-code-review-guidelines
title: Code Review Guidelines
department: Engineering
doc_type: SOP
version: "1.3"
created_date: 2023-04-10
effective_date: 2023-05-01
updated_date: 2024-02-20
author: Marcus Webb
owner: Engineering
authority_level: 2
status: current
supersedes: null
tags: code-review, engineering, quality
---

# Code Review Guidelines

## Purpose

This document describes how code review is conducted at Aurelia
Technologies, with the goal of maintaining code quality, sharing
knowledge across the team, and catching defects before they reach
production.

## Review Requirement

Every change merged into a main branch requires at least one approving
review from someone other than the author. Changes touching security-
sensitive code, such as authentication or access control logic, require
approval from a designated security reviewer in addition to a regular
code reviewer.

## What Reviewers Should Check

Reviewers are expected to check for correctness, readability,
sufficient test coverage, and adherence to the team's style guide.
Reviewers should also consider whether the change introduces
unnecessary complexity or could be simplified, and whether error
handling is adequate for the failure modes the code might encounter.

## Turnaround Time

Reviewers should aim to provide initial feedback within one business
day of a review request. If a reviewer cannot review within that
window, they should reassign the review or notify the author so an
alternative reviewer can be found.

## Size of Changes

Authors are encouraged to keep pull requests small and focused on a
single logical change, since large pull requests are harder to review
thoroughly and more likely to introduce subtle defects. Changes larger
than roughly 400 lines should generally be split unless there is a
clear reason not to, such as a large but mechanical refactor.

## Handling Disagreements

If an author and reviewer disagree on a suggested change, they should
discuss it directly rather than escalating immediately. If agreement
cannot be reached, either party may loop in the team lead for a final
decision, but this should be rare in practice.

## Automated Checks

All pull requests must pass automated linting, unit tests, and the
CI build before they are eligible for review. Reviewers are not
expected to manually verify things the automated pipeline already
checks.

## Relationship to Deployment

Passing code review is a prerequisite for deployment under the
Deployment Policy, but does not by itself authorize a deployment window
outside standard hours; see the Deployment Policy for scheduling rules.
