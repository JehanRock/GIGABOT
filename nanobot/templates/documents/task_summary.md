---
name: task_summary
description: Task completion summary document. Use to document completed tasks with approach, outcome, and changes made.
required_fields:
  - task
  - outcome
optional_fields:
  - executor
  - approach
  - files_changed
  - duration
  - tests_passed
  - lessons_learned
  - follow_up_items
  - related_tasks
---
# Task Summary: {{ task }}

**Document ID:** {{ doc_id }}
**Date:** {{ date }}
**Executor:** {{ executor | default("GigaBot") }}
**Duration:** {{ duration | default("Not tracked") }}

---

## Task Description

{{ task }}

---

## Approach

{{ approach | default("_Description of the approach taken to complete this task._") }}

---

## Outcome

{{ outcome }}

---

## Files Changed

{% for file in files_changed %}
- `{{ file }}`
{% endfor %}

---

## Testing

**Tests Passed:** {{ tests_passed | default("Not verified") }}

---

## Lessons Learned

{{ lessons_learned | default("_Key learnings from this task._") }}

---

## Follow-Up Items

{% for item in follow_up_items %}
- [ ] {{ item }}
{% endfor %}

---

## Related Tasks

{% for task in related_tasks %}
- {{ task }}
{% endfor %}

---

**Task Completed:** {{ datetime }}
