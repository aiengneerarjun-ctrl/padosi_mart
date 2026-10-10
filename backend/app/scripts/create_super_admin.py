"""Super Admin banane ki script (app me sirf ek hi Super Admin hota hai).

Chalane ka tarika:
    docker compose exec backend python -m app.scripts.create_super_admin 9876543210
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Role, User, UserRole
from app.schemas.auth import normalize_phone


async def main(raw_phone: str) -> None:
    phone = normalize_phone(raw_phone)
    async with SessionLocal() as db:
        role = await db.scalar(select(Role).where(Role.name == "SUPER_ADMIN"))
        holder = await db.scalar(select(User).join(UserRole, UserRole.user_id == User.id).where(UserRole.role_id == role.id))
        if holder is not None and holder.phone != phone:
            print(f"Super Admin pehle se maujood hai ({holder.phone}). App me sirf ek hi Super Admin ho sakta hai.")
            return
        user = await db.scalar(select(User).where(User.phone == phone))
        if user is None:
            user = User(phone=phone, roles=[])
            db.add(user)
        if role not in user.roles:
            user.roles.append(role)
        await db.commit()
    print(f"{phone} ab SUPER_ADMIN hai. Is number se OTP login karo.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Use: python -m app.scripts.create_super_admin <mobile number>")
    asyncio.run(main(sys.argv[1]))
    