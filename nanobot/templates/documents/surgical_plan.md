---
name: surgical_plan
description: Code modification instruction document for Claude Code. Use when delegating code surgery tasks to coding agents.
required_fields:
  - task_name
  - diagnosis
  - files
  - steps
optional_fields:
  - surgeon
  - chief
  - test_criteria
  - rollback_plan
  - priority
  - estimated_complexity
  - notes
---
# SURGICAL PLAN: {{ task_name }}

**Document ID:** {{ doc_id }}
**Date:** {{ date }}
**Surgeon:** {{ surgeon | default("Claude Code") }}
**Chief:** {{ chief | default("GigaBot") }}
**Priority:** {{ priority | default("Normal") }}

---

## 1. Diagnosis

{{ diagnosis }}

---

## 2. Incision Points (Files to Modify)

{% for file in files %}
- `{{ file }}`
{% endfor %}

---

## 3. Procedure Steps

Execute the following steps in order:

{% for step in steps %}
{{ loop.index }}. [ ] {{ step }}
{% endfor %}

---

## 4. Vitals (Test Criteria)

{{ test_criteria | default("Run the test suite and verify all tests pass:\n```bash\npytest\n```") }}

---

## 5. Rollback Plan

{{ rollback_plan | default("If the procedure fails, revert all changes:\n```bash\ngit checkout -- .\n```") }}

---

## 6. Post-Op Notes

{{ notes | default("_Document any observations or complications here after the procedure is complete._") }}

---

**Status:** [ ] Pre-Op | [ ] In Progress | [ ] Complete | [ ] Aborted
