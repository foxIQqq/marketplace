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
    SELECT id, name, price, category, seller_id
    FROM items
    """
    items_for_sale = await database.fetch_all(query=query_items_for_sale)
    items_for_sale = [dict(item) for item in items_for_sale]

    for item in items_for_sale:
        item["is_owned_by_user"] = user and item["seller_id"] == user["id"]

    if user:
        query_favorites = """
        SELECT item_id 
        FROM favorites 
        WHERE user_id = :user_id
        """
        favorites = await database.fetch_all(query=query_favorites, values={"user_id": user["id"]})
        favorite_ids = {fav["item_id"] for fav in favorites}
        for item in items_for_sale:
            item["is_favorite"] = item["id"] in favorite_ids

        query_cart = """
        SELECT item_id 
        FROM cart 
        WHERE user_id = :user_id
        """
        cart_items = await database.fetch_all(query=query_cart, values={"user_id": user["id"]})
        cart_item_ids = {item["item_id"] for item in cart_items}
        for item in items_for_sale:
            item["in_cart"] = item["id"] in cart_item_ids

    return templates.TemplateResponse(
        "index.html", {
            "request": request,
            "items": items_for_sale,
            "user": user,
        }
    )


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

@router.post("/cart/{item_id}")
async def add_to_cart(item_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    query_check = "SELECT 1 FROM cart WHERE item_id = :item_id AND user_id = :user_id"
    result = await database.fetch_one(query=query_check, values={"item_id": item_id, "user_id": user["id"]})

    if not result:
        query_insert = "INSERT INTO cart (item_id, user_id) VALUES (:item_id, :user_id)"
        await database.execute(query=query_insert, values={"item_id": item_id, "user_id": user["id"]})

    return RedirectResponse(url="/", status_code=303)
