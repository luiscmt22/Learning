# Python Web Service Tutorial
## From Zero to Working Service

---

# Chapter 1: What is a Web Service?

## The Restaurant Analogy

Imagine a restaurant:

```
+-------------+                      +------------------+
|   YOU       |   "I want pasta"     |    KITCHEN       |
|  (Client)   |  ----------------->  |   (Web Service)  |
|             |                      |                  |
|             |   *serves pasta*     |                  |
|             |  <-----------------  |                  |
+-------------+                      +------------------+
```

- **You** are the CLIENT (the one making requests)
- **The kitchen** is the WEB SERVICE (processes requests, returns results)
- **Your order** is the REQUEST (what you want)
- **The food** is the RESPONSE (what you get back)

You don't need to know HOW the kitchen makes the pasta. You just send an order and get food back. That's exactly how a web service works!

---

## HTTP: The Language of the Web

**HTTP** stands for **HyperText Transfer Protocol**. It's the "language" that computers use to talk to web services.

Every HTTP request has these parts:

### 1. URL (Uniform Resource Locator)
The address of the service. Like a street address for a building.

```
http://localhost:8000/api/process
│      │         │    └─────────── Path (which "room" in the building)
│      │         └──────────────── Port (which "door" to use)
│      └────────────────────────── Host (the building's address)
└───────────────────────────────── Protocol (HTTP or HTTPS)
```

- **localhost** = "this computer" (127.0.0.1)
- **8000** = the port number (like a door number)
- **/api/process** = the path (which endpoint to call)

### 2. HTTP Method (What You Want to Do)

| Method | Meaning | Real-world analogy |
|--------|---------|-------------------|
| GET | "Give me data" | Viewing a webpage, reading information |
| POST | "Here's data, process it" | Submitting a form, creating something |
| PUT | "Update this data" | Editing your profile |
| DELETE | "Remove this" | Deleting a file |

**For your web service, you'll mainly use:**
- `GET` - for checking if the service is alive (health check)
- `POST` - for sending data to be processed

### 3. Headers
Metadata about the request. Like the "from" address on an envelope.

```
Content-Type: application/json    <-- "I'm sending JSON data"
Authorization: Bearer xyz123      <-- "Here's my password/token"
```

### 4. Body (for POST requests)
The actual data you're sending. Like the letter inside the envelope.

---

## What is an Endpoint?

An **endpoint** is a specific URL that does a specific thing. Think of it like different phone extensions in an office:

```
/health       --> "Is the service running?" (dial 1)
/api/process  --> "Process this data"       (dial 2)
/docs         --> "Show me documentation"   (dial 3)
```

When you call `http://localhost:8000/health`, you're calling the `/health` endpoint.

---

## What is JSON?

**JSON** = **J**ava**S**cript **O**bject **N**otation

It's a text format for structured data. Here's an example:

```json
{
    "name": "Maria",
    "age": 28,
    "is_active": true,
    "skills": ["Python", "SQL", "FastAPI"],
    "address": {
        "city": "Lisbon",
        "country": "Portugal"
    }
}
```

**JSON Rules:**
- Use `"double quotes"` for keys and string values
- Numbers don't need quotes: `28`
- Booleans are lowercase: `true` or `false`
- Arrays use square brackets: `["item1", "item2"]`
- Objects use curly braces: `{"key": "value"}`

**Why JSON?**
- Human-readable (you can read it!)
- Machine-readable (computers can parse it easily)
- Universal (every programming language supports it)

---

## What is Serialization?

**Serialization** = Converting a Python object into JSON text

```python
# Python object (in memory)
person = {
    "name": "Maria",
    "age": 28
}

# After serialization (JSON text that can be sent over network)
'{"name": "Maria", "age": 28}'
```

**Deserialization** = The opposite (JSON text back to Python object)

**Why does this matter?**
1. Your service receives JSON text over the network
2. It converts (deserializes) to a Python object
3. Your code processes the Python object
4. It converts (serializes) the result back to JSON
5. The JSON is sent back over the network

```
Client                           Your Service
------                           ------------
JSON text  ----network---->  deserialize to Python object
                                    |
                                    v
                              process the data
                                    |
                                    v
JSON text  <---network----   serialize to JSON text
```

---

# Chapter 2: The Tools We're Using

## Python

Python is the programming language we're writing our service in.

**Why Python?**
- Easy to read and write
- Huge ecosystem of libraries
- Great for web services

**Version:** We'll use Python 3.14 (or whatever the API requires)

---

## FastAPI

**FastAPI** is a web framework. A "framework" is pre-built code that handles common tasks so you don't have to write everything from scratch.

**What FastAPI does for you:**
1. **Receives HTTP requests** - Listens for incoming connections
2. **Routes requests** - Sends each request to the right function
3. **Parses JSON** - Automatically converts JSON to Python objects
4. **Validates data** - Checks that incoming data is correct
5. **Sends responses** - Converts your Python objects back to JSON
6. **Creates documentation** - Auto-generates interactive docs at `/docs`

**Without FastAPI**, you'd need to write hundreds of lines of code to do all this yourself.

**Example of how easy FastAPI makes things:**

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
def say_hello():
    return {"message": "Hello, World!"}
```

That's it! Those 7 lines create a working web service with:
- An endpoint at `/hello`
- That returns JSON: `{"message": "Hello, World!"}`
- Plus automatic documentation at `/docs`

---

## Uvicorn

**Uvicorn** is the server that actually runs your FastAPI application.

Think of it this way:
- **FastAPI** = Your application code (the chef)
- **Uvicorn** = The server that runs it (the restaurant building)

```
Internet                Uvicorn                 FastAPI
--------                -------                 -------
Request  ---------->  Receives request  ----->  Processes it
         <----------  Sends response   <-----   Returns result
```

**Uvicorn:**
- Listens on a port (like door 8000)
- Accepts incoming connections
- Passes requests to FastAPI
- Sends FastAPI's responses back to clients

**The command to run:**
```cmd
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Breaking this down:
- `python -m uvicorn` = Run Uvicorn as a Python module
- `main:app` = In the file `main.py`, use the object called `app`
- `--reload` = Auto-restart when code changes (for development)
- `--host 0.0.0.0` = Accept connections from any IP address
- `--port 8000` = Listen on port 8000

---

## Pydantic

**Pydantic** is a library for data validation and serialization.

**What it does:**
1. **Defines data structures** - What fields your data should have
2. **Validates data** - Checks that incoming data matches the structure
3. **Serializes/deserializes** - Converts between Python and JSON

**Example:**

```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str      # Must be a string
    age: int       # Must be an integer
    active: bool   # Must be true/false

# Valid data - works fine
person = Person(name="Maria", age=28, active=True)

# Invalid data - Pydantic raises an error!
person = Person(name="Maria", age="twenty-eight", active=True)
# Error: age must be an integer, not a string
```

**Why this matters:**
- If someone sends bad data to your service, Pydantic catches it
- You get a clear error message
- Your code never sees invalid data

---

# Chapter 3: Virtual Environments (venv)

## The Problem

Imagine you have two Python projects:

```
Project A needs: requests version 2.0
Project B needs: requests version 3.0
```

If you install both system-wide, they conflict! You can only have one version installed at a time.

## The Solution: Virtual Environments

A **virtual environment** is an isolated "bubble" for your project.

```
Your Computer
├── System Python (don't touch this!)
│
├── Project A/
│   └── venv/  <-- Project A's bubble (has requests 2.0)
│
└── Project B/
    └── venv/  <-- Project B's bubble (has requests 3.0)
```

Each project has its own:
- Copy of Python
- Copy of pip
- Its own installed packages

**Benefits:**
- No conflicts between projects
- Easy cleanup (just delete the venv folder)
- Reproducible environments

## How venv Works

When you create a virtual environment, Python creates this folder structure:

```
C:\webservice\
├── venv\                         <-- The virtual environment
│   ├── Scripts\                  <-- Windows executables
│   │   ├── activate.bat          <-- Run this to "enter" the bubble
│   │   ├── deactivate.bat        <-- Run this to "exit" the bubble
│   │   ├── python.exe            <-- Python for THIS project only
│   │   └── pip.exe               <-- Pip for THIS project only
│   │
│   └── Lib\
│       └── site-packages\        <-- Where YOUR packages get installed
│           ├── fastapi/
│           ├── uvicorn/
│           └── pydantic/
│
├── main.py                       <-- Your code
├── models.py
└── requirements.txt
```

## Commands

### Create a virtual environment:
```cmd
python -m venv venv
```
- `python -m venv` = Run the venv module
- `venv` = Name of the folder to create (convention is "venv")

### Activate (enter the bubble):
```cmd
venv\Scripts\activate
```

You'll know it worked when you see `(venv)` at the start of your prompt:
```
(venv) C:\webservice>
```

### Install packages (while activated):
```cmd
pip install fastapi uvicorn pydantic
```
These install ONLY in the venv, not system-wide.

### Deactivate (exit the bubble):
```cmd
deactivate
```

The `(venv)` prefix disappears.

## Important!

**You must activate the venv every time you open a new Command Prompt!**

If you don't see `(venv)` at the start of your prompt, your packages won't be found.

---

# Chapter 4: Batch Files (.bat)

## What is a Batch File?

A **batch file** is a text file containing Windows commands. When you double-click it, Windows runs all the commands automatically.

It's like a script that types commands for you.

**File extension:** `.bat` or `.cmd`

## Why Use One?

Instead of remembering and typing:
```cmd
cd C:\webservice
venv\Scripts\activate
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You just double-click `run.bat` and it does everything!

## Our run.bat Explained

```batch
@echo off
REM ================================================
REM This batch file starts the Python web service
REM ================================================

REM @echo off = Don't show each command as it runs
REM            (without this, you'd see every command printed)

REM Display a nice header
echo ========================================
echo   Python Web Service Starter
echo ========================================
echo.

REM Activate the virtual environment
REM 'call' is needed because activate.bat is another batch file
REM Without 'call', this script would stop after activate runs
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Show helpful information
echo.
echo The service will be available at:
echo   http://localhost:8000
echo.
echo API Documentation (interactive test page):
echo   http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Start the web server
REM python -m uvicorn = Run uvicorn as a Python module
REM main:app = In main.py, use the 'app' object
REM --reload = Auto-restart when code changes
REM --host 0.0.0.0 = Accept connections from any IP
REM --port 8000 = Listen on port 8000
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

REM If the server stops (Ctrl+C or error), wait for keypress
REM This keeps the window open so you can see any errors
pause
```

## Common Batch File Commands

| Command | What it does |
|---------|-------------|
| `@echo off` | Don't print commands as they run |
| `echo Hello` | Print "Hello" to the screen |
| `echo.` | Print a blank line |
| `REM comment` | A comment (ignored by Windows) |
| `call other.bat` | Run another batch file and return |
| `pause` | Wait for user to press a key |
| `cd folder` | Change to a different folder |

---

# Chapter 5: Step-by-Step Installation Guide

## Step 1: Download Python

1. Open a browser
2. Go to: `https://www.python.org/downloads/`
3. Click the big yellow "Download Python 3.x.x" button
4. Save the installer file

## Step 2: Install Python

1. Double-click the downloaded `.exe` file
2. **CRITICAL: Check the box "Add Python to PATH"**
   - If you forget this, Python won't work from Command Prompt!
3. Click "Customize installation"
4. Make sure these are checked:
   - pip
   - py launcher
5. Click "Next"
6. Check "Install for all users" (may need admin password)
7. Click "Install"
8. Wait for completion

## Step 3: Verify Python Installation

Open Command Prompt (search "cmd" in Start menu) and type:

```cmd
python --version
```

Should show: `Python 3.14.x`

```cmd
pip --version
```

Should show: `pip 24.x.x from ...`

**If you get "not recognized":** Python wasn't added to PATH. Reinstall and check the PATH box!

## Step 4: Create Project Folder

```cmd
mkdir C:\webservice
cd C:\webservice
```

## Step 5: Create Virtual Environment

```cmd
python -m venv venv
```

This creates the `venv` folder.

## Step 6: Activate Virtual Environment

```cmd
venv\Scripts\activate
```

You should see `(venv)` at the start of your prompt.

## Step 7: Install Required Packages

```cmd
pip install fastapi uvicorn[standard] pydantic
```

Verify they installed:
```cmd
pip list
```

You should see fastapi, uvicorn, pydantic in the list.

## Step 8: Copy the Code Files

Copy these files to `C:\webservice\`:
- `main.py`
- `models.py`
- `requirements.txt`
- `run.bat`

## Step 9: Start the Server

Either:
- Double-click `run.bat`

Or in Command Prompt (with venv activated):
```cmd
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Step 10: Test It!

Open a browser and go to:
- `http://localhost:8000` - Should see welcome message
- `http://localhost:8000/health` - Should see health status
- `http://localhost:8000/docs` - Interactive API documentation!

---

# Chapter 6: Testing with Jupyter Notebook

## What is Jupyter Notebook?

Jupyter Notebook is an interactive Python environment that runs in your browser.

**Features:**
- Write code in "cells"
- Run cells one at a time
- See results immediately
- Mix code with documentation
- Great for learning and testing!

## Installing Jupyter

With your venv activated:
```cmd
pip install jupyter requests
```

- `jupyter` = The notebook environment
- `requests` = Library for making HTTP requests from Python

## Starting Jupyter

```cmd
jupyter notebook
```

This opens a browser window with the Jupyter interface.

## Using the Notebook

1. Click on `test_webservice.ipynb` to open it
2. Each gray box is a "cell" containing code
3. Click a cell to select it
4. Press `Shift+Enter` to run the cell
5. Results appear below the cell

## What Our Notebook Does

The notebook I created for you:
1. Tests if the service is running (health check)
2. Sends POST requests with different data
3. Shows how to read the responses
4. Demonstrates error handling

---

# Quick Reference Card

## Commands to Remember

```cmd
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install packages
pip install fastapi uvicorn[standard] pydantic

# Start server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Deactivate
deactivate
```

## URLs

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Welcome page |
| http://localhost:8000/health | Health check |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/api/process | Main endpoint (POST) |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "python not recognized" | Reinstall Python, check "Add to PATH" |
| "No module named fastapi" | Activate venv first! `venv\Scripts\activate` |
| "Port 8000 in use" | Use different port: `--port 8001` |
| Can't connect from other PC | Check firewall allows port 8000 |

---

# Verification Checklist

Before leaving the site, verify:

- [ ] `python --version` shows 3.14.x
- [ ] `pip --version` works
- [ ] `venv` folder exists
- [ ] `venv\Scripts\activate` shows `(venv)` prefix
- [ ] `pip list` shows fastapi, uvicorn, pydantic
- [ ] `run.bat` starts the server
- [ ] `http://localhost:8000` shows welcome message
- [ ] `http://localhost:8000/health` returns healthy
- [ ] `http://localhost:8000/docs` shows interactive docs
- [ ] POST request to `/api/process` works
- [ ] Jupyter notebook runs
