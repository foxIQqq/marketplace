from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from app.db.database import database
from app.utils.auth import get_current_user

import pandas as pd
import random
from catboost import CatBoostClassifier
from sklearn.preprocessing import MinMaxScaler

router = APIRouter()

@router.post("/train_model")
async def recommendations(request: Request, user):
    user_id = user["id"]

    # Получение всех товаров из каталога
    query_items = """
    SELECT id AS item_id, category, price 
    FROM items;
    """
    rows = await database.fetch_all(query=query_items)
    rows = [str(row) for row in rows]
    print(rows)
    catalog = pd.DataFrame(rows, columns=["item_id", "category", "price"])

    # Получение избранного
    async def get_favorites(user_id):
        query = """
        SELECT items.id AS item_id, items.category, items.price
        FROM favorites
        LEFT JOIN items ON favorites.item_id = items.id
        WHERE favorites.user_id = :user_id;
        """
        rows = await database.fetch_all(query=query, values={"user_id": user_id})
        if rows:
            df = pd.DataFrame(rows, columns=["item_id", "category", "price"])
            df["interaction"] = "favorite"
            return df
        return pd.DataFrame(columns=["item_id", "category", "price", "interaction"])

    # Получение корзины
    async def get_cart(user_id):
        query = """
        SELECT items.id AS item_id, items.category, items.price
        FROM cart
        LEFT JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = :user_id;
        """
        rows = await database.fetch_all(query=query, values={"user_id": user_id})
        if rows:
            df = pd.DataFrame(rows, columns=["item_id", "category", "price"])
            df["interaction"] = "cart"
            return df
        return pd.DataFrame(columns=["item_id", "category", "price", "interaction"])

    # Получение покупок
    async def get_purchases(user_id):
        query = """
        SELECT items.id AS item_id, items.category, items.price
        FROM purchases
        LEFT JOIN items ON purchases.item_id = items.id
        WHERE purchases.buyer_id = :user_id;
        """
        rows = await database.fetch_all(query=query, values={"user_id": user_id})
        if rows:
            df = pd.DataFrame(rows, columns=["item_id", "category", "price"])
            df["interaction"] = "buy"
            return df
        return pd.DataFrame(columns=["item_id", "category", "price", "interaction"])


    # Получение данных пользователя
    favorites = await get_favorites(user_id)
    cart = await get_cart(user_id)
    purchases = await get_purchases(user_id)

    # Проверка, есть ли данные для обучения
    if favorites.empty and cart.empty and purchases.empty:
        # Пустые рекомендации при отсутствии данных пользователя
        empty_recommendations = [{"user_id": user_id, "item_id": int(item_id)} for item_id in catalog["item_id"].sample(n=min(10, len(catalog)))]
        query_insert = """
        INSERT INTO recommendation_cache (user_id, item_id)
        VALUES (:user_id, :item_id)
        ON CONFLICT (user_id, item_id) DO NOTHING;
        """
        await database.execute_many(query=query_insert, values=empty_recommendations)
        return JSONResponse(content={"message": "Рекомендации пусты, но добавлены случайные товары"})


    user_data = pd.concat([favorites, cart, purchases], ignore_index=True)
    user_data["target"] = 1

    # Генерация отрицательных примеров
    purchased_items = user_data["item_id"]
    available_items = catalog[~catalog["item_id"].isin(purchased_items)]
    negative_samples = available_items.sample(n=min(1000, len(available_items)))
    negative_samples["target"] = 0
    negative_samples["interaction"] = "none"

    print(catalog.head())
    print(catalog.dtypes)


    # Подготовка данных для обучения
    combined = pd.concat([user_data, negative_samples], ignore_index=True)
    # Преобразование колонки 'price' в числовой формат, заменяя некорректные значения на NaN
    combined["price"] = pd.to_numeric(combined["price"], errors="coerce")

    # Проверка на наличие NaN после преобразования
    if combined["price"].isnull().any():
        raise ValueError("Некоторые значения в колонке 'price' не являются числовыми. Проверьте данные.")

    # Применение MinMaxScaler
    scaler = MinMaxScaler()
    combined["price"] = scaler.fit_transform(combined[["price"]])


    X = combined[["price", "category", "interaction"]]
    y = combined["target"]
    categorical_features = ["category", "interaction"]

    combined["sample_weight"] = combined["interaction"].map({
        "none": 0.1,
        "favorite": 0.5,
        "cart": 0.7,
        "buy": 1
    })

    # Обучение модели
    model = CatBoostClassifier(
        iterations=200,
        learning_rate=0.1,
        depth=6,
        cat_features=categorical_features,
        loss_function="Logloss",
        verbose=100
    )
    model.fit(X, y, sample_weight=combined["sample_weight"])

    # Предсказание для всех товаров
    catalog["interaction"] = "none"
    catalog["price"] = scaler.transform(catalog[["price"]])
    prediction_data = catalog[["price", "category", "interaction"]]
    catalog["score"] = model.predict_proba(prediction_data)[:, 1]

    # Выбор топ-2000 товаров
    recommendations = catalog.sort_values(by="score", ascending=False).head(2000)

    # Запись в таблицу recommendation_cache
    if not recommendations.empty:
        recommendation_rows = [{"user_id": user_id, "item_id": int(item_id)} for item_id in recommendations["item_id"]]
        query_insert = """
        INSERT INTO recommendation_cache (user_id, item_id)
        VALUES (:user_id, :item_id)
        ON CONFLICT (user_id, item_id) DO NOTHING;
        """
        await database.execute_many(query=query_insert, values=recommendation_rows)

    return JSONResponse(content={"message": "Рекомендации обновлены"})

