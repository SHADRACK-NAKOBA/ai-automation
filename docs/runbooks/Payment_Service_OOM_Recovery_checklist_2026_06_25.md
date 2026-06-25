# Payment Service OOM Recovery — Analyst Checklist
**Version:** AI-Generated from Runbook v1.2 | **Source:** Payment Service OOM Recovery Runbook (2025-01-15)
**Difficulty:** L1 | **Estimated Total Time:** [~35–45 minutes]

> **When to use this checklist:** The payment service has crashed with an OutOfMemoryError, OR monitoring shows heap memory usage above 90%.

---

## Prerequisites

Complete all of these before starting. Do not proceed if any are missing — contact your manager or the Platform Team instead.

- [ ] You can log into the Dynatrace monitoring dashboard
- [ ] You have SSH access to production servers (test with: `ssh prod-payment-01.company.com` — you should reach a login prompt)
- [ ] You have `kubectl` access to the `payment-service` namespace
- [ ] You have the Payments Engineering on-call contact saved in PagerDuty
- [ ] You have your manager's contact details available
- [ ] You have an incident ticket open and ready to update

---

## Steps

---

### Phase 1: Verify the Issue
> **Goal:** Confirm this is a real OOM event before taking any action.

- [ ] **Step 1** [~3 min]: Log into Dynatrace and check the current heap usage for the payment service.
  - Navigate to: **Applications → Payment Service → JVM Metrics → Heap Usage**
  - ✅ **Success looks like:** You can see the heap usage graph and it reads above 90%, OR you see a recent spike that caused a crash.
  - ❌ **If heap is below 90% and stable:** Do not proceed. Monitor the dashboard for 5 minutes and reassess. If it stays below 90%, close the alert as a false positive and document your finding in the incident ticket.

- [ ] **Step 2** [~1 min]: Check whether the payment service is currently responding.
  - Command:
    ```bash
    curl -f https://payments.company.com/health
    ```
  - ✅ **Success looks like (service is UP):** You receive an HTTP 200 response. The output will look similar to:
    ```
    {"status":"UP","components":{"db":{"status":"UP"}}}
    ```
    → If you see this, the service is still running. **Wait 5 minutes**, run the command again, and monitor Dynatrace. Only continue to Phase 2 if the service goes down or heap exceeds 90%.
  - ❌ **Success looks like (service is DOWN):** You see an error such as:
    ```
    curl: (22) The requested URL returned error: 503
    ```
    or the command hangs with no response. → The service is down. **Proceed immediately to Phase 2.**

---

### Phase 2: Notify the Team
> **Goal:** Ensure the right people are informed before you make any changes. Never skip this phase.

- [ ] **Step 3** [~2 min]: Post an alert in the **#incidents** Slack channel.
  - Copy and paste this message exactly:
    ```
    P1: Payment service OOM - investigating
    Service: payments.company.com
    Status: [DOWN / Heap >90% — pick one]
    Analyst: [Your Name]
    Incident Ticket: [Your Ticket Number]
    ```
  - ✅ **Success looks like:** Message is posted and visible in #incidents.

- [ ] **Step 4** [~2 min]: Page the Payments Engineering on-call engineer via PagerDuty.
  - Open PagerDuty → select policy: **payments-oncall** → trigger a new incident.
  - Title: `P1: Payment Service OOM — L1 analyst responding`
  - ✅ **Success looks like:** PagerDuty shows the alert as "Triggered" and you receive a confirmation notification.
  - ❗ **Note:** The on-call engineer may contact you. Keep your phone nearby for the rest of this procedure.

- [ ] **Step 5** [~1 min]: If the current time is **outside business hours (before 9am or after 6pm, or on a weekend)**, notify