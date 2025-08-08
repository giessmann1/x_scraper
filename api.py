#!/usr/bin/env python3
"""
X Scraper API
A FastAPI application to control the X scraper via HTTP endpoints.
"""

import json
import logging
import os
import signal
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from database_wrapper import mongo_authenticate



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


API_VERSION = "1.0.0"
API_TITLE = "X Scraper API"
API_DESCRIPTION = "REST API for controlling the X (Twitter) scraper"


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)


current_jobs: Dict[str, Dict[str, Any]] = {}
job_counter = 0
scraper_process: Optional[subprocess.Popen] = None



# Pydantic models for API requests
class ScrapeRequest(BaseModel):
    profile: str
    tweet: Optional[str] = None
    max_comments: int = 10
    max_tweets: int = 10
    attachments: bool = True
    waiting_time: int = 7
    force: str = "none"  # none, tweets, comments, both
    deep: bool = False


class JobResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    profile: str
    tweet: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, Any]
    api_version: str


class InfoResponse(BaseModel):
    api_title: str
    api_version: str
    api_description: str
    endpoints: List[str]
    scraper_status: str
    database_status: str


class SchemaResponse(BaseModel):
    database_collections: Dict[str, List[str]]
    api_endpoints: List[Dict[str, Any]]


def create_job_id() -> str:
    global job_counter
    job_counter += 1
    return f"job_{int(time.time())}_{job_counter}"


def run_scraper_process(job_id: str, scrape_params: ScrapeRequest) -> None:
    global scraper_process
    
    try:
        current_jobs[job_id]["status"] = "running"
        current_jobs[job_id]["started_at"] = datetime.now().isoformat()
        
        cmd = [
            "python", "/app/scraper.py",
            "--profile", scrape_params.profile,
            "--max-comments", str(scrape_params.max_comments),
            "--max-tweets", str(scrape_params.max_tweets),
            "--attachments", str(scrape_params.attachments).lower(),
            "--waiting-time", str(scrape_params.waiting_time),
            "--force", scrape_params.force
        ]
        
        if scrape_params.tweet:
            cmd.extend(["--tweet", scrape_params.tweet])
        
        if scrape_params.deep:
            cmd.append("--deep")
        
        logger.info(f"Starting scraper process for job {job_id}: {' '.join(cmd)}")
        
        scraper_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/app"
        )
        
        stdout, stderr = scraper_process.communicate()
        
        if scraper_process.returncode == 0:
            current_jobs[job_id]["status"] = "completed"
            current_jobs[job_id]["output"] = stdout
            logger.info(f"Job {job_id} completed successfully")
        else:
            current_jobs[job_id]["status"] = "failed"
            current_jobs[job_id]["error"] = stderr
            logger.error(f"Job {job_id} failed with error: {stderr}")
        
        current_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        current_jobs[job_id]["return_code"] = scraper_process.returncode
        
    except Exception as e:
        current_jobs[job_id]["status"] = "failed"
        current_jobs[job_id]["error"] = str(e)
        current_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        logger.error(f"Exception in job {job_id}: {e}")
    finally:
        scraper_process = None


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/info", response_model=InfoResponse)
async def get_info():
    try:
        try:
            db = mongo_authenticate("./")
            db.admin.command('ping')
            db_status = "connected (secrets-based auth)"
        except Exception:
            db_status = "disconnected"
        
        # Check scraper status
        scraper_status = "idle"
        if scraper_process and scraper_process.poll() is None:
            scraper_status = "running"
        elif any(job["status"] == "running" for job in current_jobs.values()):
            scraper_status = "running"
        
        return InfoResponse(
            api_title=API_TITLE,
            api_version=API_VERSION,
            api_description=API_DESCRIPTION,
            endpoints=[
                "/info", "/schema", "/run", "/stop", "/jobs", "/health"
            ],
            scraper_status=scraper_status,
            database_status=db_status
        )
    except Exception as e:
        logger.error(f"Error in /info endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema", response_model=SchemaResponse)
async def get_schema():
    try:
        db_collections = {
            "tweets": [
                "tweet_id_str", "datetime_utc_iso", "text_str", "username_str",
                "fullname_str", "replies_int", "reposts_int", "quotes_int",
                "likes_int", "views_video_int", "hashtags_list", "mentions_list",
                "links_list", "attachments_list", "is_repost_bool", "hash256_str"
            ],
            "comments": [
                "tweet_id_str", "datetime_utc_iso", "text_str", "username_str",
                "fullname_str", "replies_int", "reposts_int", "quotes_int",
                "likes_int", "views_video_int", "hashtags_list", "mentions_list",
                "links_list", "attachments_list", "ref_tweet_id_str",
                "profile_tweet_id_str", "depth_int", "hash256_str"
            ],
            "profile": [
                "username_str", "fullname_str", "joindate_utc_iso", "tweets_int",
                "following_int", "followers_int", "likes_int", "verified_bool",
                "bio_str", "location_str", "website_str", "category_str"
            ],
            "attachments": [
                "tweet_id_str", "attachments_list", "quote_bool"
            ]
        }
        
        api_endpoints = [
            {
                "path": "/info",
                "method": "GET",
                "description": "Get API information and status"
            },
            {
                "path": "/schema",
                "method": "GET",
                "description": "Get database schema and API endpoint information"
            },
            {
                "path": "/run",
                "method": "POST",
                "description": "Start a new scraping job",
                "parameters": {
                    "profile": "string (required) - Username to scrape",
                    "tweet": "string (optional) - Specific tweet ID to scrape",
                    "max_comments": "integer (default: 10) - Maximum comments per tweet",
                    "max_tweets": "integer (default: 10) - Maximum tweets to scrape",
                    "attachments": "boolean (default: true) - Whether to scrape attachments",
                    "waiting_time": "integer (default: 7) - Days to wait before scraping new tweets",
                    "force": "string (default: 'none') - Force rescraping: none, tweets, comments, both",
                    "deep": "boolean (default: false) - Scrape comments of comments"
                }
            },
            {
                "path": "/stop",
                "method": "POST",
                "description": "Stop the currently running scraping job"
            },
            {
                "path": "/jobs",
                "method": "GET",
                "description": "Get list of all jobs"
            },
            {
                "path": "/jobs/{job_id}",
                "method": "GET",
                "description": "Get details of a specific job"
            },
            {
                "path": "/health",
                "method": "GET",
                "description": "Get health status of all services"
            }
        ]
        
        return SchemaResponse(
            database_collections=db_collections,
            api_endpoints=api_endpoints
        )
    except Exception as e:
        logger.error(f"Error in /schema endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run")
async def run_scraper(scrape_params: ScrapeRequest, background_tasks: BackgroundTasks):
    try:
        if scraper_process and scraper_process.poll() is None:
            raise HTTPException(
                status_code=409,
                detail="Scraper is already running. Stop the current job first."
            )
        
        if not scrape_params.profile.strip():
            raise HTTPException(status_code=400, detail="Profile parameter is required")
        
        scrape_params.profile = scrape_params.profile.lstrip('@')
        
        if scrape_params.force not in ["none", "tweets", "comments", "both"]:
            raise HTTPException(
                status_code=400,
                detail="Force parameter must be one of: none, tweets, comments, both"
            )
        
        job_id = create_job_id()
        current_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "profile": scrape_params.profile,
            "tweet": scrape_params.tweet,
            "parameters": scrape_params.dict()
        }
        
        background_tasks.add_task(run_scraper_process, job_id, scrape_params)
        
        logger.info(f"Created job {job_id} for profile {scrape_params.profile}")
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"Scraping job started for profile {scrape_params.profile}",
            "profile": scrape_params.profile,
            "parameters": scrape_params.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /run endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stop")
async def stop_scraper():
    try:
        global scraper_process
        
        if not scraper_process or scraper_process.poll() is not None:
            return {
                "status": "no_running_job",
                "message": "No scraping job is currently running"
            }
        
        scraper_process.terminate()
        
        try:
            scraper_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            scraper_process.kill()
            scraper_process.wait()
        
        for job_id, job in current_jobs.items():
            if job["status"] == "running":
                job["status"] = "stopped"
                job["completed_at"] = datetime.now().isoformat()
                job["message"] = "Job stopped by user request"
        
        scraper_process = None
        logger.info("Scraper process stopped successfully")
        
        return {
            "status": "stopped",
            "message": "Scraping job stopped successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in /stop endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs")
async def get_jobs():
    try:
        jobs_list = []
        for job_id, job in current_jobs.items():
            jobs_list.append({
                "job_id": job_id,
                "status": job["status"],
                "created_at": job["created_at"],
                "profile": job["profile"],
                "tweet": job.get("tweet"),
                "completed_at": job.get("completed_at"),
                "error": job.get("error")
            })
        
        jobs_list.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "total_jobs": len(jobs_list),
            "jobs": jobs_list
        }
        
    except Exception as e:
        logger.error(f"Error in /jobs endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    try:
        if job_id not in current_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job = current_jobs[job_id].copy()
        
        if job["status"] == "running" and "started_at" in job:
            start_time = datetime.fromisoformat(job["started_at"])
            runtime = datetime.now() - start_time
            job["runtime_seconds"] = int(runtime.total_seconds())
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /jobs/{job_id} endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def get_health():
    try:
        services = {}
        
        try:
            # For Docker environment, check if MongoDB is accessible without auth if no credentials
            db = mongo_authenticate("./")
            db.admin.command('ping')
            services["database"] = {
                "status": "healthy",
                "details": {"connection": "active", "auth": "secrets-based"}
            }
        except Exception as db_error:
            services["database"] = {
                "status": "unhealthy",
                "details": {"error": str(db_error)}
            }
        
        scraper_status = "idle"
        if scraper_process and scraper_process.poll() is None:
            scraper_status = "running"
        elif any(job["status"] == "running" for job in current_jobs.values()):
            scraper_status = "running"
        
        services["scraper"] = {
            "status": "healthy",
            "details": {"current_status": scraper_status}
        }
        
        services["api"] = {
            "status": "healthy",
            "details": {"version": API_VERSION, "active_jobs": len(current_jobs)}
        }
        
        all_healthy = all(
            service.get("status") == "healthy" 
            for service in services.values()
        )
        overall_status = "healthy" if all_healthy else "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            services=services,
            api_version=API_VERSION
        )
        
    except Exception as e:
        logger.error(f"Error in /health endpoint: {e}")
        return HealthResponse(
            status="error",
            timestamp=datetime.now().isoformat(),
            services={"error": {"status": "error", "details": {"message": str(e)}}},
            api_version=API_VERSION
        )


def cleanup():
    global scraper_process
    if scraper_process and scraper_process.poll() is None:
        logger.info("Stopping scraper process...")
        scraper_process.terminate()
        try:
            scraper_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            scraper_process.kill()


def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    cleanup()
    exit(0)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    logger.info(f"Starting {API_TITLE} v{API_VERSION}")
    logger.info("API Documentation available at: http://localhost:8001/docs")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
