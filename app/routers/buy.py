from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.db.database import database
from app.utils.auth import get_current_user
from app.frontend.templates import templates

router = APIRouter()

@router.get("/buy/{item_id}", response_class=HTMLResponse)
async def buy_item_page(request: Request, item_id: int, user=Depends(get_current_user)):
    """Страница покупки скина."""
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Получаем информацию о скине и его цене
    query_item = """
    SELECT name, price, seller_id
    FROM items
    WHERE id = :item_id
    """
    item = await database.fetch_one(query=query_item, values={"item_id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Товар не найден или не доступен для продажи")

    # Получаем баланс текущего пользователя
    query_balance = "SELECT balance FROM users WHERE id = :user_id"
    user_balance = await database.fetch_one(query=query_balance, values={"user_id": user["id"]})

    return templates.TemplateResponse(
        "buy.html",
        {
            "request": request,
            "item": dict(item),
            "user_balance": user_balance["balance"],
            "user": user,
            "item_id": item_id
        },
    )

@router.post("/buy/{item_id}")
async def buy_item(item_id: int, user=Depends(get_current_user)):
    """Обработка покупки скина."""
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    async with database.transaction():
        # Получаем информацию о скине и продавце
        query_item = """
        SELECT price, seller_id, quantity
        FROM items
        WHERE id = :item_id
        """
        item = await database.fetch_one(query=query_item, values={"item_id": item_id})
        if not item:
            raise HTTPException(status_code=404, detail="Товар не найден или уже куплен")

        # Проверяем баланс покупателя
        query_balance = "SELECT balance FROM users WHERE id = :user_id"
        buyer_balance = await database.fetch_one(query=query_balance, values={"user_id": user["id"]})
        if buyer_balance["balance"] < item["price"]:
            raise HTTPException(status_code=400, detail="Недостаточно средств")

        # Проверяем доступность товара
        if item["quantity"] <= 0:
            raise HTTPException(status_code=400, detail="Товар закончился")

        # Обновляем баланс покупателя и продавца
        update_buyer_balance = """
        UPDATE users SET balance = balance - :amount WHERE id = :user_id
        """
        update_seller_balance = """
        UPDATE users SET balance = balance + :amount WHERE id = :seller_id
        """
        await database.execute(update_buyer_balance, values={"amount": item["price"], "user_id": user["id"]})
        await database.execute(update_seller_balance, values={"amount": item["price"], "seller_id": item["seller_id"]})

        # Обновляем статус продажи и инвентарь
        update_item_sale = "UPDATE items SET quantity = quantity - 1 WHERE id = :item_id"
        await database.execute(update_item_sale, values={"item_id": item_id})

        # Логируем транзакцию в таблицу transactions
        insert_transaction = """
        INSERT INTO purchases (buyer_id, seller_id, item_id, price, created_at)
        VALUES (:buyer_id, :seller_id, :item_id, :price, CURRENT_TIMESTAMP)
        """
        await database.execute(insert_transaction, values={
            "buyer_id": user["id"],
            "seller_id": item["seller_id"],
            "item_id": item_id,
            "price": item["price"]
        })

    # Редирект в профиль после успешной покупки
    return RedirectResponse(url="/profile", status_code=303)