---
name: analysis
description: Code or system analysis document. Use for architecture reviews, code audits, and technical assessments.
required_fields:
  - subject
  - findings
optional_fields:
  - analyst
  - scope
  - methodology
  - recommendations
  - severity
  - affected_components
  - evidence
  - conclusion
---
# Analysis: {{ subject }}

**Document ID:** {{ doc_id }}
**Date:** {{ date }}
**Analyst:** {{ analyst | default("GigaBot") }}
**Severity:** {{ severity | default("Informational") }}

---

## Scope

{{ scope | default("This analysis covers the subject matter as specified.") }}

---

## Methodology

{{ methodology | default("Standard code review and system analysis techniques were applied.") }}

---

## Findings

{{ findings }}

---

## Affected Components

{% for component in affected_components %}
- `{{ component }}`
{% endfor %}

---

## Evidence

{{ evidence | default("_Supporting evidence and code references._") }}

---

## Recommendations

{% for rec in recommendations %}
{{ loop.index }}. {{ rec }}
{% endfor %}

---

## Conclusion

{{ conclusion | default("_Summary of the analysis and recommended next steps._") }}

---

**Analysis Complete:** {{ datetime }}
