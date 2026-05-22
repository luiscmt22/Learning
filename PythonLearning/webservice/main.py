# =============================================================================
# main.py - The Main Web Service Application
# =============================================================================
#
# This is the entry point of your web service. When you run:
#   python -m uvicorn main:app --reload
#
# Uvicorn looks for the 'app' object in this file and starts serving it.
#
# THIS FILE CONTAINS:
#   1. FastAPI app creation
#   2. Endpoint definitions (the URLs your service responds to)
#   3. Request handling logic
#
# =============================================================================

# -----------------------------------------------------------------------------
# IMPORTS
# -----------------------------------------------------------------------------

# FastAPI is the web framework - it handles HTTP requests/responses
# HTTPException is used to return error responses with specific status codes
from fastapi import FastAPI, HTTPException

# Import our data models from models.py
# GenericRequest: defines what data clients send TO us
# GenericResponse: defines what data we send BACK to clients
from models import GenericRequest, GenericResponse


# -----------------------------------------------------------------------------
# CREATE THE FASTAPI APPLICATION
# -----------------------------------------------------------------------------

# This creates the main application object
# All our endpoints will be attached to this 'app' object
# The parameters here appear in the auto-generated documentation at /docs

app = FastAPI(
    # The title appears at the top of the /docs page
    title="Generic Web Service",

    # A description of what this API does
    description="A web service that receives requests and returns serialized responses. "
                "This is a skeleton application that you can customize for your needs.",

    # Version number (useful for tracking updates)
    version="1.0.0",

    # Additional documentation
    docs_url="/docs",           # URL for interactive Swagger UI docs
    redoc_url="/redoc",         # URL for alternative ReDoc documentation
)


# =============================================================================
# WHAT ARE DECORATORS?
# =============================================================================
#
# You'll see things like @app.get("/health") above functions.
# These are called "decorators" in Python.
#
# A decorator modifies or enhances a function. In FastAPI:
#   @app.get("/health")   means "When someone makes a GET request to /health,
#                                run the function below"
#
#   @app.post("/api/process")  means "When someone makes a POST request to
#                                      /api/process, run the function below"
#
# Think of it as "registering" your function to handle a specific URL.
#
# =============================================================================


# -----------------------------------------------------------------------------
# ENDPOINT: Root (/)
# -----------------------------------------------------------------------------

@app.get("/")
def root():
    """
    Root endpoint - just returns a welcome message.

    DECORATOR EXPLAINED:
    - @app.get("/") means:
      - This handles GET requests (reading data)
      - At the URL path "/" (the root, like http://localhost:8000/)

    FUNCTION:
    - Takes no parameters (no input needed)
    - Returns a dictionary, which FastAPI converts to JSON

    HOW TO TEST:
    - Open browser: http://localhost:8000/
    - Or use curl: curl http://localhost:8000/

    EXPECTED RESPONSE:
    {
        "message": "Welcome to the Web Service",
        "documentation": "Visit /docs for interactive API documentation",
        "health_check": "Visit /health to check service status"
    }
    """
    # Return a dictionary - FastAPI automatically converts this to JSON
    return {
        "message": "Welcome to the Web Service",
        "documentation": "Visit /docs for interactive API documentation",
        "health_check": "Visit /health to check service status"
    }


# -----------------------------------------------------------------------------
# ENDPOINT: Health Check (/health)
# -----------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """
    Health check endpoint - verifies the service is running.

    WHY HAVE A HEALTH CHECK?
    - Monitoring systems can ping this to check if the service is alive
    - Load balancers use it to know if they should send traffic here
    - You can quickly verify the service started correctly

    HOW TO TEST:
    - Open browser: http://localhost:8000/health
    - Or use curl: curl http://localhost:8000/health

    EXPECTED RESPONSE:
    {
        "status": "healthy",
        "message": "Service is running normally"
    }
    """
    return {
        "status": "healthy",
        "message": "Service is running normally"
    }


# -----------------------------------------------------------------------------
# ENDPOINT: Process Request (/api/process)
# -----------------------------------------------------------------------------

@app.post("/api/process", response_model=GenericResponse)
def process_request(request: GenericRequest):
    """
    Main endpoint for processing requests.

    DECORATOR EXPLAINED:
    - @app.post("/api/process") means:
      - This handles POST requests (sending data to be processed)
      - At the URL path "/api/process"

    - response_model=GenericResponse tells FastAPI:
      - "The response will match the GenericResponse model"
      - This adds the response structure to the /docs documentation
      - FastAPI validates our response matches this model

    FUNCTION PARAMETERS:
    - request: GenericRequest
      - FastAPI sees this type hint and automatically:
        1. Reads the JSON body from the HTTP request
        2. Validates it matches GenericRequest model
        3. Creates a GenericRequest object
        4. Passes it to this function

    HOW TO TEST:
    1. Go to http://localhost:8000/docs
    2. Click on "POST /api/process"
    3. Click "Try it out"
    4. Enter JSON like:
       {
         "action": "test",
         "data": {"key": "value"},
         "request_id": "123"
       }
    5. Click "Execute"

    EXPECTED RESPONSE:
    {
        "success": true,
        "message": "Successfully processed action: test",
        "result": {
            "received_action": "test",
            "received_data": {"key": "value"},
            "processed": true
        },
        "request_id": "123",
        "timestamp": "2024-01-15T10:30:00.123456"
    }
    """

    # -------------------------------------------------------------------------
    # TRY-EXCEPT BLOCK
    # -------------------------------------------------------------------------
    # We wrap our code in try-except to catch any errors gracefully
    # Instead of crashing, we return a proper error response

    try:
        # ---------------------------------------------------------------------
        # YOUR BUSINESS LOGIC GOES HERE
        # ---------------------------------------------------------------------
        # This is where you would add the actual processing logic.
        # For now, we just echo back what was received as a demonstration.
        #
        # EXAMPLE: If the action is "calculate", you might:
        #   if request.action == "calculate":
        #       x = request.data.get("x", 0)
        #       y = request.data.get("y", 0)
        #       result = {"sum": x + y}
        #
        # For now, we'll just show what we received:

        result = {
            "received_action": request.action,    # Echo back the action
            "received_data": request.data,        # Echo back the data
            "processed": True                     # Indicate we processed it
        }

        # ---------------------------------------------------------------------
        # BUILD AND RETURN THE RESPONSE
        # ---------------------------------------------------------------------
        # We create a GenericResponse object with all the fields
        # FastAPI will convert this to JSON automatically

        return GenericResponse(
            success=True,                                              # It worked!
            message=f"Successfully processed action: {request.action}",  # Human-readable
            result=result,                                             # The actual result
            request_id=request.request_id                              # Echo back their ID
            # Note: timestamp is set automatically by GenericResponse.__init__
        )

    except Exception as e:
        # ---------------------------------------------------------------------
        # ERROR HANDLING
        # ---------------------------------------------------------------------
        # If anything goes wrong, we catch it here and return a proper error
        # response instead of crashing the whole service

        # str(e) converts the exception to a readable error message
        error_message = f"Error processing request: {str(e)}"

        return GenericResponse(
            success=False,                    # It failed
            message=error_message,            # What went wrong
            result=None,                      # No result
            request_id=request.request_id     # Still echo back their ID
        )


# =============================================================================
# BONUS: EXAMPLE OF AN ENDPOINT WITH PATH PARAMETERS
# =============================================================================

@app.get("/api/echo/{message}")
def echo_message(message: str):
    """
    Example endpoint showing path parameters.

    PATH PARAMETERS:
    - The {message} in the URL becomes a function parameter
    - Example: GET /api/echo/hello -> message = "hello"

    HOW TO TEST:
    - Open browser: http://localhost:8000/api/echo/hello
    - Try: http://localhost:8000/api/echo/testing123

    This is useful when you need to pass simple values in the URL itself.
    """
    return {
        "you_said": message,
        "echo": message.upper()  # .upper() converts to uppercase
    }


# =============================================================================
# WHAT HAPPENS WHEN A REQUEST COMES IN
# =============================================================================
#
# Let's trace through what happens when a client sends a POST to /api/process:
#
# 1. CLIENT sends HTTP request:
#    POST /api/process HTTP/1.1
#    Content-Type: application/json
#
#    {"action": "test", "data": {"x": 1}}
#
# 2. UVICORN receives the request and passes it to FastAPI
#
# 3. FASTAPI:
#    a. Looks at the URL path (/api/process) and method (POST)
#    b. Finds the matching function: process_request
#    c. Sees the function expects request: GenericRequest
#    d. Reads the JSON body from the request
#    e. Passes the JSON to Pydantic for validation
#
# 4. PYDANTIC:
#    a. Checks if the JSON matches GenericRequest model
#    b. If valid: creates a GenericRequest object
#    c. If invalid: raises ValidationError
#
# 5. FASTAPI (continued):
#    a. If validation passed: calls process_request(request)
#    b. If validation failed: returns 422 error to client
#
# 6. YOUR CODE (process_request):
#    a. Does whatever processing you need
#    b. Returns a GenericResponse object
#
# 7. FASTAPI:
#    a. Converts GenericResponse to JSON
#    b. Sends HTTP response back to client
#
# 8. CLIENT receives JSON response
#
# =============================================================================


# =============================================================================
# RUNNING THIS FILE DIRECTLY (optional)
# =============================================================================
# Normally you run: python -m uvicorn main:app --reload
# But this code lets you also run: python main.py

if __name__ == "__main__":
    # This code only runs if you execute this file directly
    # (not when it's imported by uvicorn)

    import uvicorn

    print("Starting the web service...")
    print("Open http://localhost:8000/docs for interactive documentation")

    # Run the server
    # host="0.0.0.0" means accept connections from any IP
    # port=8000 is the port number
    # reload=True means auto-restart when code changes
    uvicorn.run(
        "main:app",      # The app to run (this file's 'app' object)
        host="0.0.0.0",  # Accept connections from anywhere
        port=8000,       # Port number
        reload=True      # Auto-reload on code changes
    )
