from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import HTTPException
from app.db.database import database
from app.utils.auth import get_current_user
from app.frontend.templates import templates
from starlette.status import HTTP_303_SEE_OTHER
# from app.utils.logger import log_history



router = APIRouter()

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user=Depends(get_current_user)):
    """Страница профиля пользователя."""
    if not user:  # Проверяем, что пользователь авторизован
        return RedirectResponse(url="/login", status_code=303)
    
    # Проверка, является ли пользователь администратором
    if user["is_admin"]:
        # Получаем список всех пользователей
        query_users = "SELECT id, username, balance FROM users"
        all_users = await database.fetch_all(query=query_users)
        all_users = [dict(u) for u in all_users]

    
        # Получаем список всех предметов на продаже
        query_items = """
        SELECT id, name
        FROM items
        """
        items_for_removal = await database.fetch_all(query=query_items)
        items_for_removal = [dict(item) for item in items_for_removal]

        return templates.TemplateResponse(
            "admin_profile.html", 
            {
                "request": request,
                "users": all_users,
                "items_for_removal": items_for_removal,
                "user": user
            }
        )

    # query_user_items = """
    # SELECT 
    #     items.name, 
    #     items.price
    #     items.id,
    # FROM inventory
    # JOIN items ON inventory.item_id = items.id
    # LEFT JOIN item_sales ON items.id = item_sales.item_id AND item_sales.status = 'active' -- Подключаем таблицу item_sales
    # WHERE inventory.user_id = :user_id
    # """
    # user_items = await database.fetch_all(query=query_user_items, values={"user_id": user["id"]})
    # user_items = [dict(item) for item in user_items]

    # Получаем баланс текущего пользователя
    query_balance = "SELECT balance FROM users WHERE id = :user_id"
    user_balance = await database.fetch_one(query=query_balance, values={"user_id": user["id"]})

    return templates.TemplateResponse(
        "profile.html", {
            "request": request,
            # "user_items": user_items,
            "balance": user_balance["balance"],
            "user": user
        }
    )

# @router.post("/remove_sale/{item_id}")
# async def remove_item_from_sale(item_id: int, request: Request, user=Depends(get_current_user)):
#     """Снять скин с продажи"""
#     # Начинаем транзакцию
#     async with database.transaction():
#         # Проверяем, принадлежит ли скин пользователю и активен ли
#         query_check_item = """
#         SELECT item_sales.id 
#         FROM item_sales
#         JOIN inventory ON item_sales.item_id = inventory.item_id
#         WHERE item_sales.item_id = :item_id 
#         AND inventory.user_id = :user_id 
#         AND item_sales.status = 'active'
#         """
#         item_sale = await database.fetch_one(query=query_check_item, values={"item_id": item_id, "user_id": user["id"]})

#         if not item_sale:
#             raise HTTPException(status_code=404, detail="Скин не найден в активных продажах")

#         # Удаляем запись из item_sales
#         query_delete_sale = """
#         DELETE FROM item_sales WHERE item_id = :item_id AND status = 'active'
#         """
#         await database.execute(query=query_delete_sale, values={"item_id": item_id})

#         # Обновляем статус в таблице inventory
#         query_update_inventory = """
#         UPDATE inventory
#         SET status = NULL
#         WHERE item_id = :item_id AND user_id = :user_id
#         """
#         await database.execute(query=query_update_inventory, values={"item_id": item_id, "user_id": user["id"]})


#     # Определяем откуда пришел запрос и редиректим
#     referer = request.headers.get("referer", "/profile")
#     return RedirectResponse(url=referer, status_code=HTTP_303_SEE_OTHER)

@router.post("/logout")
async def logout(request: Request):
    """Выход из учетной записи."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="user_id")  # Удаляем куку
    return response

@router.post("/admin/set_balance")
async def set_balance(user_id: int = Form(...), new_balance: float = Form(...), admin=Depends(get_current_user)):
    """Замена баланса пользователя администратором."""
    if not admin or not admin["is_admin"]:
        return RedirectResponse(url="/", status_code=303)

    query = "UPDATE users SET balance = :new_balance WHERE id = :user_id"
    await database.execute(query=query, values={"user_id": user_id, "new_balance": new_balance})

    return RedirectResponse(url="/profile", status_code=303)

# @router.post("/admin/remove_sale")
# async def admin_remove_sale_form(item_id: int = Form(...), admin=Depends(get_current_user)):
#     """Снятие предмета с продажи администратором через форму."""
#     if not admin or not admin["is_admin"]:
#         return RedirectResponse(url="/", status_code=303)

#     # Получаем user_id владельца скина
#     query_get_user_id = "SELECT user_id FROM inventory WHERE item_id = :item_id"
#     result = await database.fetch_one(query=query_get_user_id, values={"item_id": item_id})

#     if not result:
#         raise HTTPException(status_code=404, detail="Скин не найден в инвентаре")

#     user_id = result["user_id"]

#     # Удаляем запись из таблицы item_sales
#     query_delete_sale = "DELETE FROM item_sales WHERE item_id = :item_id"
#     await database.execute(query=query_delete_sale, values={"item_id": item_id})

#     # Обновляем статус в таблице inventory
#     query_update_inventory = """
#     UPDATE inventory
#     SET status = NULL
#     WHERE item_id = :item_id AND user_id = :user_id
#     """
#     await database.execute(query=query_update_inventory, values={"item_id": item_id, "user_id": user_id})

#     # Логируем событие
#     # await log_history(user_id=user_id, action_type="remove_sell", description=f"item_id: {item_id}")

#     return RedirectResponse(url="/profile", status_code=303)

