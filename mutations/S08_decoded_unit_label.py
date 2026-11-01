"""Adversarial control: preserve the decoded numeric value, mislabel its unit."""
from reference.s08 import solve as reference_solve


def solve(payload: dict) -> dict:
    result = reference_solve(payload)
    decoded = result.get("decoded_measurement")
    if isinstance(decoded, dict):
        # Pa is a supported but dimensionally incompatible label for the
        # temperature decoded by this fixture. No numeric value is changed.
        decoded["unit"] = "Pa"
    return result
