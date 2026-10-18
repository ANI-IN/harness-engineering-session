"""Assignment A4: rule R8 (soft delete) and filter 6 (no duplicate test).

Importing this package registers the `r8_soft_delete` check with the shipharness check registry
(`shipharness.checks.register_check`), the same way the built-in R1-R7 checks register.
"""

from a4_verification.dedup_filter import NoDuplicateTest
from a4_verification.r8_soft_delete import SoftDeleteCheck

__all__ = ["NoDuplicateTest", "SoftDeleteCheck"]
