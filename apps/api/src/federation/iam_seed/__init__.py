"""IAM seed package: idempotent bootstrap of departments, roles, permissions
and the default admin officer."""

from src.federation.iam_seed.seed import (
    build_default_departments,
    build_default_roles,
    seed,
)

__all__ = ["build_default_departments", "build_default_roles", "seed"]
