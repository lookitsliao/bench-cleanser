"""bench-cleanser: Automated contamination detection for SWE-bench evaluation benchmarks.

Identifies cases where gold patches or fail-to-pass (F2P) tests exceed the
problem description, using a dual taxonomy:
  - Axis 1: Task Contamination (8 labels, bucket-based severity)
  - Axis 2: Agent Trajectory (8 labels, behavior classification)

Taxonomy aligned with OpenAI's SWE-bench Verified audit terminology:
  - APPROACH_LOCK = "Narrow test cases"
  - WIDE_TESTS    = "Wide test cases"
"""

__version__ = "1.5.0"
