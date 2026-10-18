"""The class's S2 state layer under the name the grader loads, to grade it as a baseline:

make grade-assignment-2 SUBMISSION=section-2-state-lifecycle/assignment/solution/class_s2_layer
"""

from shipharness.harness.state.layer import StateLayer as ResumableStateLayer

__all__ = ["ResumableStateLayer"]
