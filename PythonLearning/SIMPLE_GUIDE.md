# Python Web Service - Super Simple Guide

---

## What's a Web Service?

Think of **pizza delivery**:

```
    YOU                              PIZZA SHOP
    ===                              ==========

  "I want pepperoni"  ------>    [Makes pizza]
       (REQUEST)

  [Eats pizza]        <------    "Here's your pizza"
                                   (RESPONSE)
```

**That's it!**
- You **send** what you want (request)
- They **send back** the result (response)
- You don't care HOW they made it

Your web service = the pizza shop

---

## The 4 Tools (One Line Each)

| Tool | What it does | Analogy |
|------|--------------|---------|
| **Python** | The language you write code in | The language you speak |
| **FastAPI** | Handles requests & responses | The cashier taking orders |
| **Uvicorn** | Runs your service | The building/kitchen |
| **Pydantic** | Checks data is valid | The cashier checking your order makes sense |

---

## Virtual Environment = Lunchbox

**Problem:** You bring spaghetti to work. Your coworker brings spaghetti too. Whose is whose?

**Solution:** Everyone gets their own lunchbox!

```
venv = your project's lunchbox

Your Project's Lunchbox (venv folder)
┌─────────────────────────┐
│  fastapi                │
│  uvicorn                │
│  pydantic               │
│  (only YOUR packages)   │
└─────────────────────────┘

Other projects can't touch these.
Delete the folder = empty lunchbox.
```

---

## The Only Commands You Need

### First Time Setup (do once)
```cmd
python -m venv venv              # Create lunchbox
venv\Scripts\activate            # Open lunchbox
pip install -r requirements.txt  # Put food in lunchbox
```

### Every Time You Work
```cmd
venv\Scripts\activate            # Open lunchbox
run.bat                          # Start the service
```

### Or Just...
```
Double-click run.bat             # Does everything!
```

---

## How It All Connects

```
                    THE INTERNET
                         │
                         ▼
              ┌──────────────────┐
              │     UVICORN      │  ← Listens on port 8000
              │   (the server)   │    (like a door number)
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │     FASTAPI      │  ← Routes to correct function
              │  (the cashier)   │    /health → health_check()
              └────────┬─────────┘    /api/process → process_request()
                       │
                       ▼
              ┌──────────────────┐
              │    YOUR CODE     │  ← Does the actual work
              │   (main.py)      │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │    PYDANTIC      │  ← Converts Python ↔ JSON
              │  (models.py)     │
              └──────────────────┘
```

---

## JSON = Data in Text Form

Python object:
```python
{"name": "Maria", "age": 28}
```

JSON (sent over internet):
```
{"name": "Maria", "age": 28}
```

**They look the same!** JSON is just a text format that every language understands.

---

## URLs Explained

```
http://localhost:8000/api/process
│      │         │    │
│      │         │    └── Endpoint (which function to call)
│      │         └─────── Port (door number)
│      └───────────────── Host (localhost = this computer)
└──────────────────────── Protocol (http or https)
```

**localhost** = "this computer" (for testing)
**8000** = the port (like which door to knock on)
**/api/process** = which function handles this request

---

## Thursday Cheat Sheet

### Step 1: Install Python
- Download from python.org
- **CHECK "Add to PATH"** (very important!)

### Step 2: Setup Project
```cmd
mkdir C:\webservice
cd C:\webservice
```
Copy all the files here.

### Step 3: Create Virtual Environment
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4: Run It
```cmd
run.bat
```

### Step 5: Test It
Open browser: **http://localhost:8000/docs**

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python not recognized` | Reinstall Python, check "Add to PATH" |
| `No module named X` | Run: `pip install X` |
| `Port already in use` | Change port: `--port 8001` |
| `venv not found` | Run: `python -m venv venv` first |
| Can't connect from other PC | Check Windows Firewall |

---

## The Magic Test

If you can do this, you're ready:

1. ✅ `python --version` shows a version number
2. ✅ `venv\Scripts\activate` shows `(venv)` in prompt
3. ✅ `run.bat` starts without errors
4. ✅ http://localhost:8000/docs shows a nice page
5. ✅ You can click "Try it out" and get a response

---

## Quick Glossary

| Word | Meaning |
|------|---------|
| **API** | A way for programs to talk to each other |
| **Endpoint** | A URL that does something specific |
| **GET** | "Give me data" |
| **POST** | "Here's data, do something with it" |
| **JSON** | Text format for data |
| **Port** | Door number for network traffic |
| **venv** | Isolated environment for your project |
| **Request** | What you send |
| **Response** | What you get back |

---

## You Got This!

```
Thursday Plan:
1. Install Python        (5 min)
2. Copy files            (2 min)
3. Create venv           (2 min)
4. Install packages      (2 min)
5. Run service           (1 min)
6. Test in browser       (2 min)
   ─────────────────────
   Total: ~15 minutes
```

The hard part is already done (the code). You just need to set up the environment!
