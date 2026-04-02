"""Pydantic input models for classification tools (CLP, Harmonised, REACH)."""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CLPClassificationInput(BaseModel):
    """Input for echa_get_clp_classification tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002' for Formaldehyde)",
        min_length=1,
        max_length=50,
    )


class HarmonisedClassificationInput(BaseModel):
    """Input for echa_get_harmonised_classification tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )


class REACHGHSInput(BaseModel):
    """Input for echa_get_reach_ghs tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )
    cas_number: str = Field(
        ...,
        description="CAS number of the substance (e.g., '50-00-0')",
        min_length=1,
        max_length=20,
    )


class REACHPBTInput(BaseModel):
    """Input for echa_get_reach_pbt tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )
    cas_number: str = Field(
        ...,
        description="CAS number of the substance (e.g., '50-00-0')",
        min_length=1,
        max_length=20,
    )
