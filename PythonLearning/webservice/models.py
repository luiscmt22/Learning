# =============================================================================
# models.py - Data Models for the Web Service
# =============================================================================
#
# This file defines the "shape" of our data using Pydantic.
#
# WHAT IS A MODEL?
# A model is like a blueprint or template that defines:
#   - What fields the data should have
#   - What type each field should be (string, number, etc.)
#   - Which fields are required vs optional
#
# WHY USE MODELS?
#   1. VALIDATION: If someone sends bad data, Pydantic catches it automatically
#   2. DOCUMENTATION: FastAPI uses these to generate API docs
#   3. TYPE HINTS: Your code editor can help you with autocomplete
#   4. SERIALIZATION: Converts Python objects to JSON automatically
#
# =============================================================================

# -----------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------

# BaseModel is the foundation class from Pydantic
# All our models inherit from it to get validation superpowers
from pydantic import BaseModel

# 'Any' means "any type" - useful when we don't know the exact type ahead of time
# 'Optional' means "this can be None" (not required)
from typing import Any, Optional

# datetime gives us tools to work with dates and times
from datetime import datetime


# -----------------------------------------------------------------------------
# REQUEST MODEL
# -----------------------------------------------------------------------------

class GenericRequest(BaseModel):
    """
    This model defines what data the client must send to our service.

    When someone sends a POST request to /api/process, the JSON body
    must match this structure. If it doesn't, Pydantic returns an error.

    EXAMPLE VALID JSON:
    {
        "action": "calculate",
        "data": {"x": 10, "y": 20},
        "request_id": "abc123"
    }

    EXAMPLE MINIMAL JSON (only required field):
    {
        "action": "test"
    }
    """

    # -------------------------------------------------------------------------
    # FIELD: action (REQUIRED)
    # -------------------------------------------------------------------------
    # The colon (:) followed by 'str' means "this must be a string"
    # No default value means it's REQUIRED - the request fails without it
    action: str

    # -------------------------------------------------------------------------
    # FIELD: data (OPTIONAL, defaults to empty dict)
    # -------------------------------------------------------------------------
    # dict[str, Any] means "a dictionary with string keys and any type of values"
    # The '= {}' provides a default value, making this field optional
    #
    # Examples of valid 'data':
    #   {"name": "John"}           <- string value
    #   {"count": 42}              <- integer value
    #   {"items": [1, 2, 3]}       <- list value
    #   {"nested": {"a": 1}}       <- nested dict value
    data: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # FIELD: request_id (OPTIONAL, defaults to None)
    # -------------------------------------------------------------------------
    # Optional[str] means "either a string or None"
    # This is useful for tracking requests - the client can send an ID
    # and we'll include it in the response so they can match them up
    request_id: Optional[str] = None


# -----------------------------------------------------------------------------
# RESPONSE MODEL
# -----------------------------------------------------------------------------

class GenericResponse(BaseModel):
    """
    This model defines what data our service sends back to the client.

    FastAPI automatically converts this to JSON when we return it.

    EXAMPLE RESPONSE JSON:
    {
        "success": true,
        "message": "Successfully processed action: calculate",
        "result": {"sum": 30},
        "request_id": "abc123",
        "timestamp": "2024-01-15T10:30:00.123456"
    }
    """

    # -------------------------------------------------------------------------
    # FIELD: success (REQUIRED)
    # -------------------------------------------------------------------------
    # bool means "boolean" - either True or False
    # This tells the client if their request was processed successfully
    success: bool

    # -------------------------------------------------------------------------
    # FIELD: message (REQUIRED)
    # -------------------------------------------------------------------------
    # A human-readable message explaining what happened
    # Examples:
    #   "Successfully processed action: calculate"
    #   "Error: Invalid data format"
    message: str

    # -------------------------------------------------------------------------
    # FIELD: result (OPTIONAL, defaults to None)
    # -------------------------------------------------------------------------
    # 'Any' means this can be any type: dict, list, string, number, etc.
    # This is where we put the actual result of processing the request
    # We use 'Any' because different actions might return different types
    result: Any = None

    # -------------------------------------------------------------------------
    # FIELD: request_id (OPTIONAL, defaults to None)
    # -------------------------------------------------------------------------
    # We echo back the request_id from the request (if one was sent)
    # This helps the client match responses to their requests
    request_id: Optional[str] = None

    # -------------------------------------------------------------------------
    # FIELD: timestamp (OPTIONAL, defaults to empty string)
    # -------------------------------------------------------------------------
    # When was this response created?
    # We'll fill this automatically in the __init__ method below
    timestamp: str = ""

    # -------------------------------------------------------------------------
    # CUSTOM INITIALIZATION
    # -------------------------------------------------------------------------
    def __init__(self, **data):
        """
        This method runs when we create a new GenericResponse object.

        **data means "all the keyword arguments passed in"
        For example: GenericResponse(success=True, message="OK")
        would have data = {"success": True, "message": "OK"}

        We use this to automatically set the timestamp if not provided.
        """
        # First, call the parent class's __init__ to do normal Pydantic stuff
        # 'super()' refers to the parent class (BaseModel)
        super().__init__(**data)

        # If no timestamp was provided, set it to the current time
        # datetime.now() gets the current date and time
        # .isoformat() converts it to a string like "2024-01-15T10:30:00.123456"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# =============================================================================
# HOW PYDANTIC VALIDATION WORKS
# =============================================================================
#
# When FastAPI receives a request, here's what happens:
#
# 1. Client sends JSON: {"action": "test", "data": {"x": 1}}
#
# 2. FastAPI passes the JSON to Pydantic
#
# 3. Pydantic checks:
#    - Is "action" present? Yes -> OK
#    - Is "action" a string? Yes -> OK
#    - Is "data" present? Yes -> OK (if not, use default {})
#    - Is "data" a dict? Yes -> OK
#    - Is "request_id" present? No -> use default None
#
# 4. If all checks pass:
#    - Pydantic creates a GenericRequest object
#    - Your code receives a nice Python object with .action, .data, etc.
#
# 5. If any check fails:
#    - Pydantic raises a validation error
#    - FastAPI returns a 422 error to the client with details
#    - Your code never sees the bad data!
#
# EXAMPLE ERROR RESPONSE (if action is missing):
# {
#     "detail": [
#         {
#             "loc": ["body", "action"],
#             "msg": "field required",
#             "type": "value_error.missing"
#         }
#     ]
# }
#
# =============================================================================
