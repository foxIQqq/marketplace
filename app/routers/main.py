from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.frontend.templates import templates
from app.db.database import database
from app.utils.auth import get_current_user
from typing import Optional


router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request, user: Optional[dict] = Depends(get_current_user)):
    """Главная страница."""
    query_items_for_sale = """
    SELECT items.name, items.price
    FROM items
    """
    items_for_sale = await database.fetch_all(query=query_items_for_sale)
    items_for_sale = [dict(item) for item in items_for_sale]

    # Добавляем информацию о текущем пользователе, если он авторизован
    for item in items_for_sale:
        item["is_owned_by_user"] = user and item["user_id"] == user["id"]

    # Избранные скины пользователя
    favorite_items = []
    if user:
        query_favorites = """
        SELECT items.id AS item_id, items.name, items.price
        FROM items
        JOIN favorites ON items.id = favorites.item_id
        WHERE favorites.user_id = :user_id
        """
        favorite_items = await database.fetch_all(query=query_favorites, values={"user_id": user["id"]})
        favorite_items = [dict(item) for item in favorite_items]

        # Добавляем флаг "избранное"
        for item in items_for_sale:
            item["is_favorite"] = any(fav["item_id"] == item["item_id"] for fav in favorite_items)
            item["is_owned_by_user"] = item["user_id"] == user["id"]

    return templates.TemplateResponse(
        "index.html", {
            "request": request,
            "items": items_for_sale,
            "favorite_items": favorite_items,
            "user": user,
        }
    )

# @router.post("/remove_sale/{item_id}")
# async def remove_sale(item_id: int, user=Depends(get_current_user)):
#     """Снятие предмета с продажи."""
#     if not user:
#         return RedirectResponse(url="/login", status_code=303)
    
#     # Если пользователь администратор, он может снять любой предмет
#     if user["is_admin"]:
#         query = "DELETE FROM item_sales WHERE item_id = :item_id"
#         await database.execute(query=query, values={"item_id": item_id})
#         return RedirectResponse(url="/", status_code=303)

#     # Владелец может снять только свои предметы
#     query_check = """
#     SELECT 1 FROM inventory 
#     WHERE item_id = :item_id AND user_id = :user_id
#     """
#     result = await database.fetch_one(query=query_check, values={"item_id": item_id, "user_id": user["id"]})
#     if result:
#         query = "DELETE FROM item_sales WHERE item_id = :item_id"
#         await database.execute(query=query, values={"item_id": item_id})
#     return RedirectResponse(url="/", status_code=303)

# Добавление/удаление из избранного
@router.post("/favorites/{item_id}")
async def toggle_favorite(item_id: int, user=Depends(get_current_user)):
    """Добавление или удаление предмета из избранного."""
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Проверка: предмет уже в избранном?
    query_check = "SELECT 1 FROM favorites WHERE item_id = :item_id AND user_id = :user_id"
    result = await database.fetch_one(query=query_check, values={"item_id": item_id, "user_id": user["id"]})

    if result:
        # Удаляем из избранного
        query_delete = "DELETE FROM favorites WHERE item_id = :item_id AND user_id = :user_id"
        await database.execute(query_delete, values={"item_id": item_id, "user_id": user["id"]})
    else:
        # Добавляем в избранное
        query_insert = "INSERT INTO favorites (item_id, user_id) VALUES (:item_id, :user_id)"
        await database.execute(query_insert, values={"item_id": item_id, "user_id": user["id"]})

    return RedirectResponse(url="/", status_code=303)