"""Shared resume texts for the AJI-027 General Resume Intelligence tests."""

STRONG_RESUME = """Jane Doe
jane@example.com | 555-123-4567

SUMMARY
Machine learning engineer building production systems.

PROFESSIONAL EXPERIENCE
Senior ML Engineer, Acme Corp, 2020 - 2024
- Built a real-time fraud detection pipeline in Python processing 2M events per day.
- Led migration of the model serving stack to Kubernetes, reducing latency by 35%.

EDUCATION
B.S. Computer Science, State University, 2018

SKILLS
Python, Kubernetes
"""

WEAK_RESUME = """Jane Doe
jane@example.com | 555-123-4567

SUMMARY
Machine learning engineer with experience building production systems.

PROFESSIONAL EXPERIENCE
Senior ML Engineer, Acme Corp, 2020 - 2024
- Built a real-time fraud detection pipeline in Python processing 2M events per day.
- Led migration of the model serving stack to Kubernetes, reducing latency by 35%.
- Responsible for the data quality checks for the feature store.
- Worked on various dashboards for the analytics team.

EDUCATION
B.S. Computer Science, State University, 2018

SKILLS
Python, Kubernetes, Docker
"""

WEAK_BULLET_1 = "- Responsible for the data quality checks for the feature store."
WEAK_BULLET_2 = "- Worked on various dashboards for the analytics team."
