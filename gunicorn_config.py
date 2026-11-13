"""
Gunicorn Production Server Configuration for Render Deployment.

Reads environment variables supplied by Render, with production defaults.
"""

import os
import multiprocessing

# Network Binding: Render dynamically assigns a port via the PORT environment variable
port = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Worker Processes & Concurrency
# For Render Free / Starter instances (0.5 to 1 vCPU), 2 to 4 workers is ideal.
workers = int(os.getenv("WEB_CONCURRENCY", 2))
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_class = "gthread"

# Timeouts: Allow ample buffer (120s) for remote cloud DB latency and cold starts
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
graceful_timeout = 30
keepalive = 5

# Logging: Output directly to stdout and stderr for Render's live log streams
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# Security: Forwarded headers configuration when running behind Render's reverse proxy
forwarded_allow_ips = "*"
proxy_allow_ips = "*"
proxy_protocol = False

