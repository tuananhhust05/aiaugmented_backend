from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import connect_to_mongo, close_mongo_connection
from routers import auth, groq, workspaces, nodes, messages, summary

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title="FastAPI MongoDB Authentication",
    description="API đăng ký và đăng nhập với MongoDB",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(groq.router)
app.include_router(workspaces.router)
app.include_router(nodes.router)
app.include_router(messages.router)
app.include_router(summary.router)

@app.get("/")
async def root():
    return {"message": "FastAPI MongoDB Authentication API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

