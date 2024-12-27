from fastapi import APIRouter, Request, Depends, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from app.db.database import database
from app.utils.auth import get_current_user
from app.frontend.templates import templates
from app.routers.recommendation import recommendations
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

    query_cart = """
    SELECT cart.id, items.name, items.price, cart.is_selected 
    FROM cart
    JOIN items ON cart.item_id = items.id
    WHERE cart.user_id = :user_id
    """
    cart_items = await database.fetch_all(query=query_cart, values={"user_id": user["id"]})
    total_selected_price = sum(item["price"] for item in cart_items if item["is_selected"])

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
            "cart_items": [dict(item) for item in cart_items],
            "total_selected_price": total_selected_price
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
    full_name: str = Form(default=None),
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

    # Товары на продаже (confirmed)
    query_items = """
    SELECT item_name, category, price, quantity
    FROM seller_request
    WHERE user_id = :seller_id AND status = 'confirmed'
    """
    sell_items = await database.fetch_all(query=query_items, values={"seller_id": user["id"]})

    # Товары в рассмотрении (pending)
    query_pending_requests = """
    SELECT sr.item_name, sr.category, sr.price, sr.quantity
    FROM seller_request AS sr
    WHERE sr.user_id = :seller_id AND sr.status = 'pending'
    """
    pending_requests = await database.fetch_all(query=query_pending_requests, values={"seller_id": user["id"]})

    # Отклоненные заявки (denied)
    query_denied_items = """
    SELECT sr.item_name, sr.category, sr.price, sr.quantity
    FROM seller_request AS sr
    WHERE sr.user_id = :seller_id AND sr.status = 'denied'
    """
    denied_items = await database.fetch_all(query=query_denied_items, values={"seller_id": user["id"]})

    return templates.TemplateResponse(
        "sells.html", {
            "request": request,
            "user": user,
            "sell_items": [dict(item) for item in sell_items],
            "pending_requests": [dict(request) for request in pending_requests],
            "denied_items": [dict(item) for item in denied_items],
        }
    )


@router.post("/profile/sells/add")
async def add_new_item_request(
    user=Depends(get_current_user),
    full_name: str = Form(default=None),
    item_name: str = Form(default=None),
    quantity: int = Form(default=None),
    price: float = Form(default=None),
    category: str = Form(default=None),
    file: UploadFile = None
):
    """Подача заявки на добавление нового товара."""
    if not user or not user["is_seller"]:
        return RedirectResponse(url="/profile", status_code=303)
    
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

    return RedirectResponse(url="/profile/sells", status_code=303)


@router.post("/cart/remove/{cart_id}")
async def remove_from_cart(cart_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    query_delete = "DELETE FROM cart WHERE id = :cart_id AND user_id = :user_id"
    await database.execute(query=query_delete, values={"cart_id": cart_id, "user_id": user["id"]})
    return RedirectResponse(url="/profile", status_code=303)


@router.post("/cart/toggle/{cart_id}")
async def toggle_cart_item(cart_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    query_toggle = """
    UPDATE cart
    SET is_selected = NOT is_selected
    WHERE id = :cart_id AND user_id = :user_id
    """
    await database.execute(query=query_toggle, values={"cart_id": cart_id, "user_id": user["id"]})
    return RedirectResponse(url="/profile", status_code=303)

@router.post("/cart/buy")
async def buy_selected_items(user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    query_selected_items = """
    SELECT cart.id, items.price, items.id AS item_id
    FROM cart
    JOIN items ON cart.item_id = items.id
    WHERE cart.user_id = :user_id AND cart.is_selected = TRUE
    """
    selected_items = await database.fetch_all(query=query_selected_items, values={"user_id": user["id"]})
    total_price = sum(item["price"] for item in selected_items)

    # Проверяем баланс пользователя
    query_balance = "SELECT balance FROM users WHERE id = :user_id"
    user_balance = await database.fetch_one(query=query_balance, values={"user_id": user["id"]})

    if user_balance["balance"] < total_price:
        return RedirectResponse(url="/profile?error=low_balance", status_code=303)

    # Списываем средства и добавляем товары в купленные
    query_update_balance = """
    UPDATE users SET balance = balance - :total_price WHERE id = :user_id
    """
    await database.execute(query_update_balance, values={"total_price": total_price, "user_id": user["id"]})

    for item in selected_items:
        query_add_purchase = """
        INSERT INTO purchases (buyer_id, item_id) VALUES (:user_id, :item_id)
        """
        await database.execute(query_add_purchase, values={"user_id": user["id"], "item_id": item["item_id"]})

        query_remove_from_cart = "DELETE FROM cart WHERE id = :cart_id"
        await database.execute(query_remove_from_cart, values={"cart_id": item["id"]})

    return RedirectResponse(url="/profile", status_code=303)



@router.post("/logout")
async def logout(request: Request, user=Depends(get_current_user)):
    """Выход из учетной записи."""

    if user:  # Проверяем, что пользователь авторизован
        await recommendations(request, user)  # Запускаем обновление recommendation_cache

    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="user_id")  # Удаляем куку
    return response
