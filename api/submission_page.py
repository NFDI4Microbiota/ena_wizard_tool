"""
ENA Submission API
==================

This API provides an endpoint for submitting a full ENA submission JSON document 
to the ENA Webin REST V2 service.

Submission Details:
  - Test endpoint: https://wwwdev.ebi.ac.uk/ena/submit/webin-v2/submit
  - Production endpoint: https://www.ebi.ac.uk/ena/submit/webin-v2/submit
  - Authentication: Basic HTTP Authentication using your Webin credentials.

Endpoint:
  /submit - Submits a full ENA submission JSON document.

How to run:
  Run this file with Uvicorn:
    uvicorn submission:app --reload

Interactive documentation is available at:
  http://localhost:8000/docs

Author: Your Name
Date: YYYY-MM-DD
"""

import requests
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Any, Dict

app = FastAPI(
    title="ENA Submission API",
    description="API for submitting a full ENA submission JSON document to the ENA Webin REST V2 service.",
    version="1.0.0"
)

class ENASubmissionRequest(BaseModel):
    """
    Model for an ENA submission request.
    
    Attributes:
      - username: Your Webin username for ENA authentication.
      - password: Your Webin password for ENA authentication.
      - mode: Submission mode; either "test" or "production".
      - submission: The full ENA submission JSON document.
    """
    username: str = Field(..., example="your_webin_username")
    password: str = Field(..., example="your_webin_password")
    mode: str = Field(..., example="test", description="Either 'test' or 'production'")
    submission: Dict[str, Any] = Field(
        ...,
        example={
            "submission": {
                "alias": "submissionAliasName",
                "accession": "",
                "actions": [{"type": "ADD"}]
            },
            "projects": [
                {
                    "alias": "comparative-analysis",
                    "name": "Human Gut Microbiota Study",
                    "title": "Exploration of human gastric microbiota",
                    "description": "The genome sequences of gut microbes were obtained...",
                    "attributes": [{"tag": "testTag", "value": "testValue"}]
                }
            ],
            "samples": [
                {
                    "alias": "stomach_microbiota",
                    "title": "human gastric microbiota, mucosal",
                    "organism": {"taxonId": "1284369"},
                    "attributes": [
                        {"tag": "collection date", "value": "2010-01-20"},
                        {"tag": "host body site", "value": "Mucosa of stomach"}
                    ]
                }
            ]
        },
        description="A JSON document conforming to ENA submission format"
    )

class ENASubmissionResponse(BaseModel):
    """
    Model for the ENA submission response.
    
    This model wraps the receipt returned by the ENA submission service.
    """
    success: bool
    receipt: Dict[str, Any] = None
    error: str = None

@app.post("/submit", response_model=ENASubmissionResponse)
def submit_ena_data(request: ENASubmissionRequest):
    """
    Submit a full ENA submission JSON document to the ENA Webin REST V2 service.
    
    The endpoint uses Basic HTTP Authentication and sends the submission document 
    as a JSON payload. The URL is chosen based on the 'mode' field.
    
    Example:
      POST /submit
      {
          "username": "your_webin_username",
          "password": "your_webin_password",
          "mode": "test",
          "submission": { ... full submission JSON ... }
      }
      
    Returns:
      The receipt from ENA if successful; otherwise, an error message.
    """
    mode_lower = request.mode.lower()
    if mode_lower == "test":
        url = "https://wwwdev.ebi.ac.uk/ena/submit/webin-v2/submit"
    elif mode_lower == "production":
        url = "https://www.ebi.ac.uk/ena/submit/webin-v2/submit"
    else:
        raise HTTPException(status_code=400, detail="Mode must be either 'test' or 'production'")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            url,
            json=request.submission,
            headers=headers,
            auth=(request.username, request.password),
            timeout=60  # Adjust the timeout as needed
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error during submission: {e}")

    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=f"ENA submission error: {response.text}")

    try:
        receipt = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing ENA response: {e}")

    return ENASubmissionResponse(success=True, receipt=receipt)

# Main block to run the API directly.
if __name__ == '__main__':
    import uvicorn
    uvicorn.run("submission:app", host="0.0.0.0", port=8000, reload=True)
