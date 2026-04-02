"""Pydantic input models for substance-related tools."""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class SubstanceInfoInput(BaseModel):
    """Input for echa_get_substance_info tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002' for Formaldehyde). "
                    "Can be found on ECHA CHEM website substance page URLs.",
        min_length=1,
        max_length=50,
    )


class DossierListInput(BaseModel):
    """Input for echa_list_dossiers tool."""
    model_config = ConfigDict(str_strip_whitespace=True)

    substance_index: str = Field(
        ...,
        description="ECHA substance index (e.g., '100.000.002')",
        min_length=1,
        max_length=50,
    )
    status: Optional[str] = Field(
        default="Active",
        description="Registration status filter: 'Active' or 'Not active'",
    )
