from fastapi import APIRouter, Request, Depends, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from app.db.database import database
from app.utils.auth import get_current_user
from app.frontend.templates import templates
from starlette.status import HTTP_303_SEE_OTHER
import csv

router = APIRouter()

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user=Depends(get_current_user)):
    """Страница профиля пользователя."""
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Получаем баланс текущего пользователя
    query_balance = "SELECT balance FROM users WHERE id = :user_id"
    user_balance = await database.fetch_one(query=query_balance, values={"user_id": user["id"]})

    # Проверяем статус заявки на становление продавцом
    query_seller_request = """
    SELECT status FROM seller_request WHERE user_id = :user_id
    """
    seller_request = await database.fetch_one(query=query_seller_request, values={"user_id": user["id"]})
    is_seller_request_pending = seller_request and seller_request["status"] == "pending"

    # Получаем избранные товары
    query_favorites = """
    SELECT items.id AS item_id, items.name, items.price 
    FROM favorites 
    JOIN items ON favorites.item_id = items.id 
    WHERE favorites.user_id = :user_id
    """
    favorites = await database.fetch_all(query=query_favorites, values={"user_id": user["id"]})

    # Получаем купленные товары
    query_purchases = """
    SELECT items.name, items.price 
    FROM purchases 
    JOIN items ON purchases.item_id = items.id 
    WHERE purchases.buyer_id = :user_id
    """
    purchases = await database.fetch_all(query=query_purchases, values={"user_id": user["id"]})

    return templates.TemplateResponse(
        "profile.html", {
            "request": request,
            "balance": user_balance["balance"],
            "user": user,
            "favorites": [dict(favorite) for favorite in favorites],
            "purchases": [dict(purchase) for purchase in purchases],
            "is_seller_request_pending": is_seller_request_pending,
        }
    )

@router.get("/profile/become_a_seller", response_class=HTMLResponse)
async def become_seller_page(request: Request, user=Depends(get_current_user)):
    """Страница подачи заявки на становление продавцом."""
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("become_a_seller.html", {"request": request, "user": user})


@router.post("/profile/become_a_seller")
async def submit_seller_request(
    user=Depends(get_current_user),
    full_name: str = Form(...),
    item_name: str = Form(None),
    quantity: int = Form(None),
    price: float = Form(None),
    category: str = Form(None),
    file: UploadFile = None
):
    """Обработка заявки на становление продавцом."""
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if file:
        contents = await file.read()
        reader = csv.DictReader(contents.decode("utf-8").splitlines())
        items = [row for row in reader]
    else:
        items = [{"item_name": item_name, "quantity": quantity, "price": price, "category": category}]

    query = """
    INSERT INTO seller_request (user_id, full_name, item_name, quantity, price, category, status) 
    VALUES (:user_id, :full_name, :item_name, :quantity, :price, :category, 'pending')
    """
    for item in items:
        await database.execute(
            query=query,
            values={
                "user_id": user["id"],
                "full_name": full_name,
                "item_name": item["item_name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "category": item["category"],
            },
        )

    return RedirectResponse(url="/profile", status_code=303)

@router.get("/profile/sells", response_class=HTMLResponse)
async def sells_page(request: Request, user=Depends(get_current_user)):
    """Страница управления продажами."""
    if not user or not user["is_seller"]:
        return RedirectResponse(url="/profile", status_code=303)

    query_items = """
    SELECT name, category, price, quantity 
    FROM items 
    WHERE seller_id = :seller_id
    """
    sell_items = await database.fetch_all(query=query_items, values={"seller_id": user["id"]})
    sell_items = [dict(item) for item in sell_items]

    return templates.TemplateResponse(
        "sells.html", {
            "request": request,
            "user": user,
            "sell_items": sell_items  # Передаём sell_items, как ожидает шаблон
        }
    )


@router.post("/logout")
async def logout(request: Request):
    """Выход из учетной записи."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="user_id")  # Удаляем куку
    return response
