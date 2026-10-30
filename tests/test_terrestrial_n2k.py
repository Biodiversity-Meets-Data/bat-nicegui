"""Tests for Natura 2000 workflow parameters."""

import pytest

from bats.terrestrial_n2k import TerrestrialN2kParameters
from bats.workflow import WorkflowValidationError


def test_n2k_parameters_serialize_year_bounds() -> None:
    parameters = TerrestrialN2kParameters(min_year=2020, max_year=2026)

    assert parameters.to_workflow_parameters() == {
        "min_year": "2020",
        "max_year": "2026",
    }
    assert parameters.to_parameter_metadata() == {"min_year": 2020, "max_year": 2026}


def test_n2k_parameters_reject_reversed_year_bounds() -> None:
    parameters = TerrestrialN2kParameters(min_year=2026, max_year=2020)

    with pytest.raises(WorkflowValidationError, match="Start year"):
        parameters.validate_input()
