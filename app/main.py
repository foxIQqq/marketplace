from fastapi import FastAPI
# from app.auth import router as steam_router
from app.routers.auth_routes import router as auth_router
from app.routers import main, profile, sell, buy
from app.db.database import database
from fastapi.staticfiles import StaticFiles
from app.utils.triggers import initialize_triggers
from app.utils.views import initialize_views

app = FastAPI()

# Подключение статики
app.mount("/static", StaticFiles(directory="app/frontend/static"), name="static")

# Подключение маршрутов
# app.include_router(steam_router)
app.include_router(profile.router)
app.include_router(main.router)
# app.include_router(sell.router)
app.include_router(buy.router)
app.include_router(auth_router)

# Подключение к базе данных при старте приложения
@app.on_event("startup")
async def startup():
    await database.connect()
    # await initialize_triggers()
    # await initialize_views()

# Отключение от базы данных при завершении приложения
@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()