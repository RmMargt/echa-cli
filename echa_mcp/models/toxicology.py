"""Pydantic input models for toxicology tools."""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ToxicologySummaryInput(BaseModel):
    """Input for echa_get_toxicology_summary tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002' for Formaldehyde)",
        min_length=1,
        max_length=50,
    )


class ToxicologyStudiesInput(BaseModel):
    """Input for echa_get_toxicology_studies tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )
    section: Optional[str] = Field(
        default=None,
        description="Optional: filter to a specific subsection (e.g., '7.2' for acute toxicity, "
                    "'7.5' for repeated dose toxicity). If not specified, returns all sections.",
    )


class ToxicologyFullInput(BaseModel):
    """Input for echa_get_toxicology_full tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )
