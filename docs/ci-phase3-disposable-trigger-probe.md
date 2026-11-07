# Disposable CI Phase 3 Trigger Probe

This file is used solely to verify GitHub Actions event behavior. This branch is not intended for merging into `dev` or `main`.

Event 1: feature-branch commit before opening a pull request.

Event 2: commit after PR opened; expect exactly one pull_request execution of each of the three workflows and no push execution.
