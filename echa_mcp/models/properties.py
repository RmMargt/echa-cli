"""Pydantic input models for physicochemical and ecotoxicology tools."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PhyschemInput(BaseModel):
    """Input for echa_get_physchem_data tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )
    section: Optional[str] = Field(
        default=None,
        description="Optional Section 4 subsection filter (e.g., '4.8' for water solubility).",
    )
    max_studies: int = Field(
        default=50,
        description="Maximum study documents to parse per query.",
        ge=0,
        le=400,
    )


class EcotoxicologyInput(BaseModel):
    """Input for echa_get_ecotoxicology_data tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )
    section: Optional[str] = Field(
        default=None,
        description="Optional Section 5/6 subsection filter (e.g., '5.1.1' or '6.1.1').",
    )
    max_studies: int = Field(
        default=50,
        description="Maximum study documents to parse per query.",
        ge=0,
        le=400,
    )
