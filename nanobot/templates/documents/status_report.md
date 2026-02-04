---
name: status_report
description: Periodic project status update report. Use for daily/weekly progress summaries and stakeholder updates.
required_fields:
  - period
  - completed
optional_fields:
  - project_name
  - author
  - in_progress
  - blockers
  - next_steps
  - metrics
  - highlights
  - risks
---
# Status Report: {{ period }}

**Document ID:** {{ doc_id }}
**Date:** {{ date }}
**Project:** {{ project_name | default("GigaBot") }}
**Author:** {{ author | default("GigaBot") }}

---

## Executive Summary

This report covers the {{ period }} period.

---

## Completed Items

{% for item in completed %}
- [x] {{ item }}
{% endfor %}

---

## In Progress

{% for item in in_progress %}
- [ ] {{ item }}
{% endfor %}

---

## Blockers & Issues

{% for blocker in blockers %}
- **Blocker:** {{ blocker }}
{% endfor %}

{{ blockers | default("_No blockers at this time._") }}

---

## Next Steps

{% for step in next_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}

---

## Highlights

{{ highlights | default("_Key achievements and milestones from this period._") }}

---

## Risks & Concerns

{{ risks | default("_No significant risks identified._") }}

---

## Metrics

{{ metrics | default("_Relevant metrics and KPIs will be tracked here._") }}

---

**Report Generated:** {{ datetime }}
