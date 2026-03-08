#!/bin/bash
# Azure App Service startup command
cd /app
poetry run uvicorn redactor.main:app --host 0.0.0.0 --port 8000
