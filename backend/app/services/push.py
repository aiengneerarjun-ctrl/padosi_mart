"""Push notification (Firebase FCM, HTTP v1).

- Notification pehle inbox me save hoti hai (services/notification.py). Push uska SIRF extra sandesha hai:
  push fail ho jaye to bhi inbox me notification rehti hai, aur order / payment par koi asar nahi padta.
- Bhejne ka kaam alag job karta hai (python -m app.jobs.send_push --loop). Wo `notifications.pushed_at IS NULL` wali nayi rows uthata hai.
- Har notification ek hi baar bhejne ki koshish hoti hai (pehle pushed_at lagta hai, phir bhejte hain), isliye double push nahi jati.
  Bahut purani (MAX_AGE_MINUTES se zyada) notification par push nahi bhejte: "10 ghante purana order aaya" bhejna bekaar hai.
- Text user ki bhasha (users.language) me banta hai, inbox jaisa hi.
- Token / service-account kabhi log me nahi aata.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import timedelta

import httpx
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DeviceToken, Notification, User
from app.services.notification import render

logger = logging.getLogger("padosi.push")

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
MAX_TOKENS_PER_USER = 10  # ek user ke zyada se zyada itne phone; purane hat jate hain
BATCH_SIZE = 50
MAX_AGE_MINUTES = 10
PARALLEL_SENDS = 10

OK, INVALID_TOKEN, ERROR = "OK", "INVALID_TOKEN", "ERROR"


# ---------- Token register / hatana ----------

async def register_device(db: AsyncSession, user: User, token: str, platform: str) -> None:
    """Token jodo. Wahi token pehle kisi aur user ke naam tha to ab is user ka ho jata hai (phone par naya login)."""
    await db.execute(
        pg_insert(DeviceToken)
        .values(user_id=user.id, token=token, platform=platform)
        .on_conflict_do_update(
            index_elements=[DeviceToken.token],
            set_={"user_id": user.id, "platform": platform, "last_seen_at": func.now()},
        )
    )
    newest = (
        select(DeviceToken.id).where(DeviceToken.user_id == user.id).order_by(DeviceToken.last_seen_at.desc()).limit(MAX_TOKENS_PER_USER)
    )
    await db.execute(delete(DeviceToken).where(DeviceToken.user_id == user.id, DeviceToken.id.not_in(newest)))
    await db.commit()


async def unregister_device(db: AsyncSession, user: User, token: str) -> int:
    """Logout par token hatao. Doosre ka token ya pehle se hata hua token = 0 (error nahi)."""
    res = await db.execute(delete(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user.id))
    await db.commit()
    return res.rowcount or 0


# ---------- FCM ----------

def classify_response(status: int, body: str) -> str:
    """FCM ke jawab se tay karo: bhej diya / token ab bekaar (hata do) / koi aur gadbad (token rehne do)."""
    if 200 <= status < 300:
        return OK
    low = body.lower()
    if status == 404 or "unregistered" in low or "sender_id_mismatch" in low or "senderid mismatch" in low:
        return INVALID_TOKEN
    if status == 400 and "registration token" in low:
        return INVALID_TOKEN
    return ERROR


def build_message(token: str, title: str, body: str, data: dict) -> dict:
    return {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": {k: str(v) for k, v in data.items()},  # FCM data me sirf string chalti hai
            "android": {"priority": "HIGH"},
        }
    }


class FcmClient:
    def __init__(self, service_account_file: str = "", http: httpx.AsyncClient | None = None, project_id: str | None = None, token_provider=None):
        self._file = service_account_file
        self._http = http or httpx.AsyncClient(timeout=10)
        self._project_id = project_id
        self._token_provider = token_provider or self._google_access_token
        self._creds = None
        self._lock = asyncio.Lock()

    def _google_access_token(self) -> str:  # thread me chalta hai (google-auth sync hai)
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        if self._creds is None:
            self._creds = service_account.Credentials.from_service_account_file(self._file, scopes=[FCM_SCOPE])
            self._project_id = self._creds.project_id
        if not self._creds.valid:
            self._creds.refresh(Request())
        return self._creds.token

    async def send(self, token: str, title: str, body: str, data: dict) -> str:
        try:
            async with self._lock:  # ek saath kai send hon to access token ek hi baar bane
                access = await asyncio.to_thread(self._token_provider)
            r = await self._http.post(
                f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send",
                headers={"Authorization": f"Bearer {access}"},
                json=build_message(token, title, body, data),
            )
        except Exception as e:  # network / credentials ki gadbad: push chhoot sakti hai, kaam nahi rukta
            logger.warning("FCM send failed: %s", type(e).__name__)
            return ERROR
        result = classify_response(r.status_code, r.text)
        if result == ERROR:
            logger.warning("FCM error status=%s", r.status_code)
        return result

    async def close(self) -> None:
        await self._http.aclose()


# ---------- Nayi notifications ko push karna ----------

async def push_pending(db: AsyncSession, client: FcmClient, batch: int = BATCH_SIZE) -> tuple[int, int, int]:
    """Nayi notifications ko push bhejo. Return: (kitni notifications uthayi, kitni push gayi, kitne bekaar token hataye)."""
    pick = (
        select(Notification.id)
        .where(Notification.pushed_at.is_(None), Notification.created_at > func.now() - timedelta(minutes=MAX_AGE_MINUTES))
        .order_by(Notification.created_at)
        .limit(batch)
        .with_for_update(skip_locked=True)  # do job ek saath chalein to ek notification ek hi uthaye
    )
    claimed = list(
        (
            await db.execute(
                update(Notification).where(Notification.id.in_(pick)).values(pushed_at=func.now())
                .returning(Notification.id).execution_options(synchronize_session=False)
            )
        ).scalars()
    )
    await db.commit()
    if not claimed:
        return 0, 0, 0

    notes = list(await db.scalars(select(Notification).where(Notification.id.in_(claimed)).order_by(Notification.created_at)))
    user_ids = {n.user_id for n in notes}
    langs = dict((await db.execute(select(User.id, User.language).where(User.id.in_(user_ids)))).all())
    tokens: dict = defaultdict(list)
    for uid, tok in (await db.execute(select(DeviceToken.user_id, DeviceToken.token).where(DeviceToken.user_id.in_(user_ids)))).all():
        tokens[uid].append(tok)

    jobs = []
    for n in notes:
        out = render(n, langs.get(n.user_id) or "en")
        data = {"code": n.code, "notification_id": n.id}
        if n.order_id:
            data["order_id"] = n.order_id
        jobs += [(tok, out.title, out.body, data) for tok in tokens.get(n.user_id, [])]

    sem = asyncio.Semaphore(PARALLEL_SENDS)

    async def one(job):
        async with sem:
            return job[0], await client.send(*job)

    results = await asyncio.gather(*(one(j) for j in jobs))
    bad = {tok for tok, res in results if res == INVALID_TOKEN}
    if bad:
        await db.execute(delete(DeviceToken).where(DeviceToken.token.in_(bad)))
        await db.commit()
    return len(claimed), sum(1 for _, res in results if res == OK), len(bad)
