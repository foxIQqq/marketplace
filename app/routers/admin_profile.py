from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.db.database import database
from app.utils.auth import get_current_user
from app.frontend.templates import templates

router = APIRouter()

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, admin=Depends(get_current_user)):
    """Страница администратора."""
    if not admin or not admin["is_admin"]:
        return RedirectResponse(url="/", status_code=303)

    # Получаем список заявок продавцов
    query_requests = """
    SELECT id, user_id, full_name, item_name, quantity, price, category 
    FROM seller_request 
    WHERE status = 'pending'
    """
    seller_requests = await database.fetch_all(query=query_requests)

    query_users = "SELECT id, username, balance FROM users"
    all_users = await database.fetch_all(query=query_users)
    all_users = [dict(u) for u in all_users]

    return templates.TemplateResponse(
        "admin_profile.html", {
            "request": request,
            "admin": admin,
            "seller_requests": [dict(request) for request in seller_requests],
            "users": all_users
        }
    )

@router.post("/admin/set_balance")
async def set_balance(user_id: int = Form(...), new_balance: float = Form(...), admin=Depends(get_current_user)):
    """Замена баланса пользователя администратором."""
    if not admin or not admin["is_admin"]:
        return RedirectResponse(url="/", status_code=303)

    query = "UPDATE users SET balance = :new_balance WHERE id = :user_id"
    await database.execute(query=query, values={"user_id": user_id, "new_balance": new_balance})

    return RedirectResponse(url="/admin", status_code=303)

@router.post("/admin/approve_request")
async def approve_request(request_id: int = Form(...), admin=Depends(get_current_user)):
    """Одобрение заявки продавца."""
    if not admin or not admin["is_admin"]:
        return RedirectResponse(url="/", status_code=303)

    # Получаем user_id по request_id
    query_get_user_id = "SELECT user_id FROM seller_request WHERE id = :request_id"
    result = await database.fetch_one(query=query_get_user_id, values={"request_id": request_id})
    if not result:
        return RedirectResponse(url="/admin", status_code=303)

    user_id = result["user_id"]

    # Обновляем статус заявки
    query_update_status = "UPDATE seller_request SET status = 'confirmed' WHERE id = :request_id"
    await database.execute(query=query_update_status, values={"request_id": request_id})

    # Устанавливаем флаг is_seller = TRUE для пользователя
    query_set_is_seller = "UPDATE users SET is_seller = TRUE WHERE id = :user_id"
    await database.execute(query=query_set_is_seller, values={"user_id": user_id})

    # Переносим товары в таблицу items
    query_transfer_items = """
    INSERT INTO items (name, category, price, quantity, seller_id)
    SELECT item_name, category, price, quantity, user_id
    FROM seller_request
    WHERE id = :request_id
    """
    await database.execute(query=query_transfer_items, values={"request_id": request_id})

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/deny_request")
async def deny_request(request_id: int = Form(...), admin=Depends(get_current_user)):
    """Отклонение заявки продавца."""
    if not admin or not admin["is_admin"]:
        return RedirectResponse(url="/", status_code=303)

    # Обновляем статус заявки
    query_update_status = "UPDATE seller_request SET status = 'denied' WHERE id = :request_id"
    await database.execute(query=query_update_status, values={"request_id": request_id})

    return RedirectResponse(url="/admin", status_code=303)
