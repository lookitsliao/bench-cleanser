"""bench-cleanser: Automated contamination detection for SWE-bench evaluation benchmarks.

Identifies cases where gold patches or fail-to-pass (F2P) tests exceed the
problem description, using a dual taxonomy:
  - Axis 1: Task Contamination (7 labels, bucket-based severity)
  - Axis 2: Agent Trajectory (8 labels, behavior classification)

Taxonomy aligned with OpenAI's SWE-bench Verified audit terminology:
  - APPROACH_LOCK = "Narrow test cases"
  - OVER_TEST     = "Wide test cases"
"""

__version__ = "1.2.0"
