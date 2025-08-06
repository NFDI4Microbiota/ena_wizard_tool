"""
ENA Metadata Field Validation API
===================================

This API provides a single endpoint for validating individual metadata
field values against predefined regular expressions. It is intended to be used
as a validation layer before submission to ENA.

Endpoint:
  /validate - Validates a metadata field value.

How to run:
  Run this file with Uvicorn:
    uvicorn validation:app --reload

Interactive documentation is available at:
  http://localhost:8000/docs

Author: Your Name
Date: YYYY-MM-DD
"""

import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="ENA Metadata Field Validation API",
    description="API to validate individual metadata fields against predefined regex patterns.",
    version="1.0.0"
)

# Dictionary mapping metadata field keys to their corresponding regex patterns.
# The keys are prefixed by category:
#   - project_: project-level metadata
#   - site_: site-level metadata
#   - sample_: sample-level metadata
#   - host_: host-level metadata
regex_dict = {
    # Project metadata
    "project_project_name": r".+",

    # Site metadata
    "site_collection_date": r"^(([0-2][0-9]{3})\-((1[0-2])|([1-9]))\-((3[0-1])|([1-2][0-9])|([0-9])))$",
    "site_Collected_by": r".+",
    "site_geo_loc_name": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+): ([^\s-]{1,2}|[^\s-]+.+[^\s-]+), ([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "site_lat": r"^(-?((?:[0-8]?[0-9](?:\.\d{0,8})?)|90))$",
    "site_lon": r"^(-?[0-9]+(?:\.[0-9]{0,8})?|-?(1[0-7]{1,2}))$",
    "site_elev": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "site_alt": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "site_depth": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "site_env_broad_scale": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]$",
    "site_env_local_scale": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]$",
    "site_env_medium": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]$",
    "site_chem_administration": (
        r"^([^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]\;"
        r"(([0-2][0-9]{3})\-([0-1]?[0-9])\-([0-3]?[0-9]))T"
        r"(([0-1][0-9]|2[0-3]):[0-5][0-9]"
        r"(?:\:[0-5][0-9])?(?:Z|[+-](?:[0-1][0-9]|2[0-3]):[0-5][0-9]))$"
    ),
    "site_temp": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "site_salinity": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "site_pH": r"^\b(?:14(?:\.0+)?|1[0-3](?:\.\d+)?|0(?:\.\d+)?|[1-9](?:\.\d+)?)(?=\b)$",

    # Sample metadata
    "sample_samp_name": r".+",
    "sample_source_mat_id": r".+",
    "sample_samp_size": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "sample_temp": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "sample_salinity": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "sample_ph": r"^\b(?:14(?:\.0+)?|1[0-3](?:\.\d+)?|0(?:\.\d+)?|[1-9](?:\.\d+)?)(?=\b)$",
    "sample_samp_taxon_id": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[NCBITaxon:\d+\]$",
    "sample_samp_collect_method": (
        r"^(?:PMID:\d+|doi:10\.\d{2,9}/.*|https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\."
        r"[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)|(?:[^\s-]{1,2}|[^\s-]+.+[^\s-]+))$"
    ),
    "sample_Microbial_isolate": r"^(yes|no)$",
    "sample_microb_cult_med": (
        r"^(?:(?:[^\s-]{1,2}|[^\s-]+.+[^\s-]+)|"
        r"((?:[^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]))$"
    ),
    "sample_chem_administration": (
        r"^([^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]\;"
        r"(([0-2][0-9]{3})\-([0-1]?[0-9])\-([0-3]?[0-9]))T"
        r"(([0-1][0-9]|2[0-3]):[0-5][0-9]"
        r"(?:\:[0-5][0-9])?(?:Z|[+-](?:[0-1][0-9]|2[0-3]):[0-5][0-9]))$"
    ),

    # Host metadata
    "host_host_taxid": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[NCBITaxon:\d+\]$",
    "host_host_common_name": r".+",
    "host_host_height": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "host_host_length": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "host_host_tot_mass": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "host_host_body_site": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]$",
    "host_host_body_product": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]$",
    "host_host_age": r"^[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?(?: *- *[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)? *([^\s-]{1,2}|[^\s-]+.+[^\s-]+)$",
    "host_host_sex": r"^(female|male|other|unknown)$",
    "host_host_diet": r"^([^\s-]{1,2}|[^\s-]+.+[^\s-]+) \[[a-zA-Z]{2,}:[a-zA-Z0-9]\d+\]$",
    "host_host_disease_stat": r".*",
}

class ValidationRequest(BaseModel):
    """
    Model for a single field validation request.
    
    Attributes:
      - metadata: The key identifying the metadata field.
      - value: The value to be validated.
    """
    metadata: str = Field(..., example="site_collection_date")
    value: str = Field(..., example="2013-03-25")

class ValidationResponse(BaseModel):
    """
    Model for the validation response.
    
    Attributes:
      - valid: Boolean indicating if the value is valid.
      - metadata: The metadata field that was validated.
      - value: The submitted value.
      - error: Error message if validation fails.
    """
    valid: bool
    metadata: str
    value: str
    error: str = None

@app.post("/validate", response_model=ValidationResponse)
def validate_data(request: ValidationRequest):
    """
    Validate a metadata field value against its regex pattern.
    
    Example:
      POST /validate
      {
          "metadata": "site_collection_date",
          "value": "2013-03-25"
      }
      
    Returns:
      A JSON response indicating if the value is valid.
    """
    if request.metadata not in regex_dict:
        raise HTTPException(status_code=400, detail="Unsupported metadata field")
    
    pattern = regex_dict[request.metadata]
    if re.fullmatch(pattern, request.value):
        return ValidationResponse(valid=True, metadata=request.metadata, value=request.value)
    else:
        return ValidationResponse(
            valid=False,
            metadata=request.metadata,
            value=request.value,
            error="Value does not match the required format"
        )

# Main block to run the API directly.
if __name__ == '__main__':
    import uvicorn
    uvicorn.run("validation:app", host="0.0.0.0", port=8000, reload=True)
