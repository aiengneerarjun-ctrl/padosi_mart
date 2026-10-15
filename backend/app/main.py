import os
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import admin, admin_catalog, admin_deliveries, admin_delivery, admin_delivery_cash,admin_delivery_earnings,admin_payments, admin_returns,admin_settlements, auth, cart, catalog, checkout, customer, delivery, health,notifications, orders,payments, product_images, products,seller_earnings, seller_orders, seller_returns, sellers, shop, stores, users
from app.core.config import settings
from app.core.i18n import DEFAULT_LANG, resolve_lang, translate

app = FastAPI(title="Padosi API", version="0.11.0")


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    # Har request ko ek ID milti hai. Audit log aur error dhoondhne me kaam aati hai.
    request.state.request_id = uuid.uuid4().hex
    # App Accept-Language header me en / hi / bho bhejti hai; yahin se bhasha tay hoti hai.
    request.state.lang = resolve_lang(request.headers.get("accept-language"))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Content-Language"] = request.state.lang
    return response


def _error_body(request: Request, code: str, message: str, **extra) -> dict:
    return {"detail": {"code": code, "message": message, **extra, "request_id": getattr(request.state, "request_id", None)}}


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    lang = getattr(request.state, "lang", DEFAULT_LANG)
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code, message = detail["code"], translate(detail["code"], lang, detail.get("message"))
    else:
        code, message = f"HTTP_{exc.status_code}", str(detail)
    return JSONResponse(_error_body(request, code, message), status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    lang = getattr(request.state, "lang", DEFAULT_LANG)
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        _error_body(request, "VALIDATION_ERROR", translate("VALIDATION_ERROR", lang), errors=errors), status_code=422
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(sellers.router, prefix="/api/v1")
app.include_router(stores.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(product_images.router, prefix="/api/v1")
app.include_router(admin_catalog.router, prefix="/api/v1")
app.include_router(shop.router, prefix="/api/v1")
app.include_router(customer.router, prefix="/api/v1")
app.include_router(cart.router, prefix="/api/v1")
app.include_router(checkout.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(seller_orders.router, prefix="/api/v1")
app.include_router(delivery.router, prefix="/api/v1")
app.include_router(admin_delivery.router, prefix="/api/v1")
app.include_router(admin_delivery_cash.router, prefix="/api/v1")
app.include_router(admin_delivery_earnings.router, prefix="/api/v1")
app.include_router(admin_deliveries.router, prefix="/api/v1")
app.include_router(admin_returns.router, prefix="/api/v1")
app.include_router(seller_returns.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(admin_settlements.router, prefix="/api/v1")
app.include_router(seller_earnings.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(admin_payments.router, prefix="/api/v1")

# Dev me photos yahin se dikhti hain (production me S3/CDN se, tab ye block chalta hi nahi)
if settings.storage_backend == "local":
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")