from __future__ import annotations

import secrets
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

REFERRAL_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
REFERRAL_CODE_LENGTH = 8
SUPPORT_USERNAME_KEY = "support_username"
EARNING_ENABLED_KEY = "earning_enabled"
EARNING_PERCENT_KEY = "earning_percent"
TRIAL_ENABLED_KEY = "trial_enabled"
TRIAL_TRAFFIC_GB_KEY = "trial_traffic_gb"
TRIAL_DAYS_KEY = "trial_days"


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def generate_referral_code(length: int = REFERRAL_CODE_LENGTH) -> str:
    return "".join(secrets.choice(REFERRAL_ALPHABET) for _ in range(length))


def normalize_referral_code(value: str | None) -> str:
    if not value:
        return ""
    return "".join(char for char in value.strip().lower() if char in REFERRAL_ALPHABET)


def normalize_support_username(value: str | None) -> str:
    if not value:
        return ""
    username = value.strip()
    username = username.removeprefix("https://t.me/").removeprefix("http://t.me/")
    username = username.removeprefix("t.me/")
    username = username.removeprefix("@")
    username = username.strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        return ""
    return username


@dataclass(slots=True)
class User:
    id: int
    telegram_id: int
    role: str
    wallet_balance: int
    referral_code: str
    referred_by: int | None
    is_blocked: bool = False
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


@dataclass(slots=True)
class PricingSettings:
    per_gb_price: int
    three_month_extra_price: int
    one_month_enabled: bool
    three_month_enabled: bool


@dataclass(slots=True)
class TrafficPreset:
    id: int
    gb: int
    discount_percent: int
    active: bool


@dataclass(slots=True)
class PurchaseOffer:
    traffic_gb: int
    duration_days: int
    source: str
    discount_percent: int
    base_price: int
    duration_extra: int
    final_price: int


@dataclass(slots=True)
class Payment:
    id: int
    user_id: int
    amount: int
    screenshot_file_id: str
    status: str
    created_at: str = ""


@dataclass(slots=True)
class WalletTransaction:
    id: int
    user_id: int
    amount: int
    reason: str
    created_at: str


@dataclass(slots=True)
class RequiredChat:
    id: int
    chat_id: int
    title: str
    invite_link: str


@dataclass(slots=True)
class PendingPaymentView:
    payment: Payment
    user: User


@dataclass(slots=True)
class Ticket:
    id: int
    user_id: int
    subject: str
    status: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class TicketMessage:
    id: int
    ticket_id: int
    sender_role: str
    text: str
    created_at: str


@dataclass(slots=True)
class DiscountCode:
    id: int
    code: str
    discount_percent: int
    max_uses: int
    used_count: int
    active: bool
    expires_at: str | None


@dataclass(slots=True)
class SalesReport:
    subscription_count: int
    subscription_revenue: int
    wallet_charges: int
    wallet_charge_total: int


@dataclass(slots=True)
class Subscription:
    id: int
    user_id: int
    plan_id: int | None
    marzban_username: str
    subscription_url: str
    expires_at: str
    traffic_gb: int
    duration_days: int
    discount_percent: int
    base_price: int
    duration_extra: int
    final_price: int
    purchase_source: str
    status: str


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    async def connect(self) -> aiosqlite.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        return db

    async def init(self) -> None:
        async with self.session() as db:
            await db.executescript(SCHEMA)
            await self._migrate(db)
            await db.commit()

    @asynccontextmanager
    async def session(self):
        db = await self.connect()
        try:
            yield db
        finally:
            await db.close()

    async def _migrate(self, db: aiosqlite.Connection) -> None:
        subscription_info = await db.execute_fetchall("PRAGMA table_info(subscriptions)")
        plan_id_info = next((row for row in subscription_info if row["name"] == "plan_id"), None)
        if plan_id_info and plan_id_info["notnull"]:
            await db.execute("PRAGMA foreign_keys = OFF")
            await db.executescript(
                """
                CREATE TABLE subscriptions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    plan_id INTEGER REFERENCES plans(id),
                    marzban_username TEXT NOT NULL,
                    subscription_url TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    traffic_gb INTEGER NOT NULL,
                    duration_days INTEGER NOT NULL DEFAULT 30,
                    discount_percent INTEGER NOT NULL DEFAULT 0,
                    base_price INTEGER NOT NULL DEFAULT 0,
                    duration_extra INTEGER NOT NULL DEFAULT 0,
                    final_price INTEGER NOT NULL DEFAULT 0,
                    purchase_source TEXT NOT NULL DEFAULT 'legacy',
                    status TEXT NOT NULL CHECK (status IN ('active', 'expired', 'disabled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                INSERT INTO subscriptions_new (
                    id, user_id, plan_id, marzban_username, subscription_url, expires_at, traffic_gb,
                    duration_days, discount_percent, base_price, duration_extra, final_price, purchase_source,
                    status, created_at, updated_at
                )
                SELECT
                    id, user_id, NULL, marzban_username, subscription_url, expires_at, traffic_gb,
                    30, 0, 0, 0, 0, 'legacy', status, created_at, updated_at
                FROM subscriptions;

                DROP TABLE subscriptions;
                ALTER TABLE subscriptions_new RENAME TO subscriptions;
                """
            )
            await db.execute("PRAGMA foreign_keys = ON")
            subscription_info = await db.execute_fetchall("PRAGMA table_info(subscriptions)")
        existing_columns = {row["name"] for row in subscription_info}
        subscription_columns = {
            "duration_days": "INTEGER NOT NULL DEFAULT 30",
            "discount_percent": "INTEGER NOT NULL DEFAULT 0",
            "base_price": "INTEGER NOT NULL DEFAULT 0",
            "duration_extra": "INTEGER NOT NULL DEFAULT 0",
            "final_price": "INTEGER NOT NULL DEFAULT 0",
            "purchase_source": "TEXT NOT NULL DEFAULT 'legacy'",
        }
        for column, definition in subscription_columns.items():
            if column not in existing_columns:
                await db.execute(f"ALTER TABLE subscriptions ADD COLUMN {column} {definition}")
        await db.execute("DELETE FROM plans")
        await db.execute(
            """
            INSERT OR IGNORE INTO pricing_settings
                (id, per_gb_price, three_month_extra_price, one_month_enabled, three_month_enabled, updated_at)
            VALUES (1, 0, 0, 1, 1, ?)
            """,
            (utcnow(),),
        )
        for gb in DEFAULT_PRESET_GB:
            await db.execute(
                """
                INSERT OR IGNORE INTO traffic_presets (gb, discount_percent, active, updated_at)
                VALUES (?, 0, 1, ?)
                """,
                (gb, utcnow()),
            )
        await self._normalize_existing_referral_codes(db)
        user_info = await db.execute_fetchall("PRAGMA table_info(users)")
        user_columns = {row["name"] for row in user_info}
        if "is_blocked" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
        if "first_name" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
            await db.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
            await db.execute("ALTER TABLE users ADD COLUMN username TEXT")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS required_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL DEFAULT '',
                invite_link TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                subject TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('open', 'closed')) DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                sender_role TEXT NOT NULL CHECK (sender_role IN ('buyer', 'admin')),
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trial_grants (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                granted_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                discount_percent INTEGER NOT NULL CHECK (discount_percent >= 0 AND discount_percent <= 100),
                max_uses INTEGER NOT NULL DEFAULT 0,
                used_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    async def _normalize_existing_referral_codes(self, db: aiosqlite.Connection) -> None:
        rows = await db.execute_fetchall("SELECT id, referral_code FROM users ORDER BY id ASC")
        used: set[str] = set()
        for row in rows:
            code = normalize_referral_code(row["referral_code"])
            if not code or code in used:
                code = await self._generate_unique_referral_code(db, used)
            used.add(code)
            if code != row["referral_code"]:
                await db.execute("UPDATE users SET referral_code = ?, updated_at = ? WHERE id = ?", (code, utcnow(), row["id"]))

    async def _generate_unique_referral_code(self, db: aiosqlite.Connection, reserved: set[str] | None = None) -> str:
        reserved = reserved or set()
        while True:
            code = generate_referral_code()
            if code in reserved:
                continue
            async with db.execute("SELECT 1 FROM users WHERE referral_code = ?", (code,)) as cur:
                exists = await cur.fetchone()
            if not exists:
                return code


class Repository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def ensure_user(
        self,
        telegram_id: int,
        admin_ids: set[int],
        *,
        referred_by: int | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
    ) -> User:
        role = "admin" if telegram_id in admin_ids else "buyer"
        row = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        if row:
            updates: list[str] = []
            params: list[object] = []
            if row["role"] != role:
                updates.append("role = ?")
                params.append(role)
            for column, value in (
                ("first_name", first_name),
                ("last_name", last_name),
                ("username", username),
            ):
                if value is not None and row[column] != value:
                    updates.append(f"{column} = ?")
                    params.append(value)
            if updates:
                updates.append("updated_at = ?")
                params.append(utcnow())
                params.append(telegram_id)
                await self.db.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?",
                    tuple(params),
                )
                await self.db.commit()
                row = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            return self._user(row)

        while True:
            referral_code = await self._generate_unique_referral_code()
            try:
                await self.db.execute(
                    """
                    INSERT INTO users (
                        telegram_id, role, wallet_balance, referral_code, referred_by,
                        first_name, last_name, username, created_at, updated_at
                    )
                    VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (telegram_id, role, referral_code, referred_by, first_name, last_name, username, utcnow(), utcnow()),
                )
                break
            except aiosqlite.IntegrityError:
                continue
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return self._user(row)

    async def ensure_user_from_telegram(
        self,
        from_user,
        admin_ids: set[int],
        *,
        referred_by: int | None = None,
    ) -> User:
        return await self.ensure_user(
            from_user.id,
            admin_ids,
            referred_by=referred_by,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            username=from_user.username,
        )

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        row = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return self._user(row) if row else None

    async def get_user(self, user_id: int) -> User | None:
        row = await self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._user(row) if row else None

    async def sync_telegram_profile(
        self,
        telegram_id: int,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
    ) -> User | None:
        row = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        if not row:
            return None
        updates: list[str] = []
        params: list[object] = []
        for column, value in (
            ("first_name", first_name),
            ("last_name", last_name),
            ("username", username),
        ):
            if value is not None and row[column] != value:
                updates.append(f"{column} = ?")
                params.append(value)
        if not updates:
            return self._user(row)
        updates.append("updated_at = ?")
        params.append(utcnow())
        params.append(telegram_id)
        await self.db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?",
            tuple(params),
        )
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return self._user(row)

    async def get_user_by_referral_code(self, code: str) -> User | None:
        normalized = normalize_referral_code(code)
        if not normalized:
            return None
        row = await self._fetchone("SELECT * FROM users WHERE referral_code = ?", (normalized,))
        return self._user(row) if row else None

    async def set_referred_by_if_empty(self, user_id: int, referrer_id: int) -> bool:
        cur = await self.db.execute(
            "UPDATE users SET referred_by = ?, updated_at = ? WHERE id = ? AND referred_by IS NULL AND id != ?",
            (referrer_id, utcnow(), user_id, referrer_id),
        )
        await self.db.commit()
        return cur.rowcount > 0

    async def _generate_unique_referral_code(self) -> str:
        while True:
            code = generate_referral_code()
            row = await self._fetchone("SELECT 1 FROM users WHERE referral_code = ?", (code,))
            if not row:
                return code

    async def list_users(self, limit: int = 20) -> list[User]:
        rows = await self._fetchall("SELECT * FROM users ORDER BY id DESC LIMIT ?", (limit,))
        return [self._user(row) for row in rows]

    async def count_users(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS total FROM users")
        return int(row["total"]) if row else 0

    async def list_users_page(self, *, page: int, per_page: int = 8) -> list[User]:
        safe_page = max(page, 1)
        offset = (safe_page - 1) * per_page
        rows = await self._fetchall(
            "SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        )
        return [self._user(row) for row in rows]

    async def search_users(self, query: str, *, limit: int = 20) -> list[User]:
        raw = query.strip()
        if not raw:
            return []
        username_query = raw.lstrip("@").lower()
        name_query = raw.lower()
        referral_query = normalize_referral_code(raw) or raw.lower()
        rows = await self._fetchall(
            """
            SELECT * FROM users
            WHERE CAST(telegram_id AS TEXT) LIKE ?
               OR LOWER(COALESCE(username, '')) LIKE ?
               OR LOWER(COALESCE(first_name, '')) LIKE ?
               OR LOWER(COALESCE(last_name, '')) LIKE ?
               OR LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))) LIKE ?
               OR LOWER(referral_code) LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                f"%{raw}%",
                f"%{username_query}%",
                f"%{name_query}%",
                f"%{name_query}%",
                f"%{name_query}%",
                f"%{referral_query}%",
                limit,
            ),
        )
        return [self._user(row) for row in rows]

    def _user_search_where(self, query: str) -> tuple[str, tuple]:
        raw = query.strip()
        username_query = raw.lstrip("@").lower()
        name_query = raw.lower()
        referral_query = normalize_referral_code(raw) or raw.lower()
        clause = """
            CAST(telegram_id AS TEXT) LIKE ?
               OR LOWER(COALESCE(username, '')) LIKE ?
               OR LOWER(COALESCE(first_name, '')) LIKE ?
               OR LOWER(COALESCE(last_name, '')) LIKE ?
               OR LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))) LIKE ?
               OR LOWER(referral_code) LIKE ?
        """
        params = (
            f"%{raw}%",
            f"%{username_query}%",
            f"%{name_query}%",
            f"%{name_query}%",
            f"%{name_query}%",
            f"%{referral_query}%",
        )
        return clause, params

    async def count_search_users(self, query: str) -> int:
        if not query.strip():
            return 0
        clause, params = self._user_search_where(query)
        row = await self._fetchone(f"SELECT COUNT(*) AS total FROM users WHERE {clause}", params)
        return int(row["total"]) if row else 0

    async def search_users_page(self, query: str, *, page: int, per_page: int = 8) -> list[User]:
        if not query.strip():
            return []
        clause, params = self._user_search_where(query)
        offset = (max(page, 1) - 1) * per_page
        rows = await self._fetchall(
            f"SELECT * FROM users WHERE {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, per_page, offset),
        )
        return [self._user(row) for row in rows]

    def _user_filter_clause(self, filter_type: str) -> tuple[str, tuple]:
        if filter_type == "blocked":
            return "is_blocked = 1", ()
        if filter_type == "funded":
            return "wallet_balance > 0", ()
        if filter_type == "with_subs":
            return "EXISTS (SELECT 1 FROM subscriptions s WHERE s.user_id = users.id)", ()
        return "1=1", ()

    async def count_users_filtered(self, filter_type: str = "all") -> int:
        clause, params = self._user_filter_clause(filter_type)
        row = await self._fetchone(f"SELECT COUNT(*) AS total FROM users WHERE {clause}", params)
        return int(row["total"]) if row else 0

    async def list_users_filtered_page(self, *, filter_type: str = "all", page: int, per_page: int = 8) -> list[User]:
        clause, params = self._user_filter_clause(filter_type)
        offset = (max(page, 1) - 1) * per_page
        rows = await self._fetchall(
            f"SELECT * FROM users WHERE {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, per_page, offset),
        )
        return [self._user(row) for row in rows]

    async def set_user_blocked(self, user_id: int, *, blocked: bool) -> User | None:
        user = await self.get_user(user_id)
        if user is None or user.role == "admin":
            return None
        await self.db.execute(
            "UPDATE users SET is_blocked = ?, updated_at = ? WHERE id = ?",
            (1 if blocked else 0, utcnow(), user_id),
        )
        await self.db.commit()
        return await self.get_user(user_id)

    async def adjust_wallet(self, user_id: int, amount: int, reason: str, linked_payment_id: int | None = None, linked_subscription_id: int | None = None) -> None:
        await self.db.execute("UPDATE users SET wallet_balance = wallet_balance + ?, updated_at = ? WHERE id = ?", (amount, utcnow(), user_id))
        await self.db.execute(
            """
            INSERT INTO wallet_transactions (user_id, amount, reason, linked_payment_id, linked_subscription_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, amount, reason, linked_payment_id, linked_subscription_id, utcnow()),
        )

    async def create_payment(self, user_id: int, amount: int, screenshot_file_id: str) -> Payment:
        cur = await self.db.execute(
            """
            INSERT INTO payments (user_id, requested_amount, screenshot_file_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (user_id, amount, screenshot_file_id, utcnow(), utcnow()),
        )
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM payments WHERE id = ?", (cur.lastrowid,))
        return self._payment(row)

    async def review_payment(self, payment_id: int, admin_user_id: int, approved: bool) -> Payment | None:
        async with self.db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)) as cur:
            row = await cur.fetchone()
        if not row or row["status"] != "pending":
            return None
        status = "approved" if approved else "declined"
        await self.db.execute(
            "UPDATE payments SET status = ?, reviewed_by = ?, updated_at = ? WHERE id = ?",
            (status, admin_user_id, utcnow(), payment_id),
        )
        if approved:
            await self.adjust_wallet(row["user_id"], row["requested_amount"], "payment_approved", linked_payment_id=payment_id)
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))
        return self._payment(row)

    async def list_pending_payments(self) -> list[Payment]:
        rows = await self._fetchall("SELECT * FROM payments WHERE status = 'pending' ORDER BY id DESC")
        return [self._payment(row) for row in rows]

    async def count_pending_payments(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS total FROM payments WHERE status = 'pending'")
        return int(row["total"]) if row else 0

    async def list_pending_payments_page(self, *, page: int, per_page: int = 8) -> list[PendingPaymentView]:
        offset = (max(page, 1) - 1) * per_page
        rows = await self._fetchall(
            """
            SELECT p.*, u.id AS u_id, u.telegram_id, u.role, u.wallet_balance, u.referral_code,
                   u.referred_by, u.is_blocked, u.first_name, u.last_name, u.username
            FROM payments p
            JOIN users u ON u.id = p.user_id
            WHERE p.status = 'pending'
            ORDER BY p.id DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        )
        return [self._pending_payment_view(row) for row in rows]

    async def get_payment(self, payment_id: int) -> Payment | None:
        row = await self._fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))
        return self._payment(row) if row else None

    async def get_pending_payment_view(self, payment_id: int) -> PendingPaymentView | None:
        row = await self._fetchone(
            """
            SELECT p.*, u.id AS u_id, u.telegram_id, u.role, u.wallet_balance, u.referral_code,
                   u.referred_by, u.is_blocked, u.first_name, u.last_name, u.username
            FROM payments p
            JOIN users u ON u.id = p.user_id
            WHERE p.id = ?
            """,
            (payment_id,),
        )
        return self._pending_payment_view(row) if row else None

    async def count_wallet_transactions(self, user_id: int) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS total FROM wallet_transactions WHERE user_id = ?", (user_id,))
        return int(row["total"]) if row else 0

    async def list_wallet_transactions(self, user_id: int, *, limit: int = 10, offset: int = 0) -> list[WalletTransaction]:
        rows = await self._fetchall(
            "SELECT * FROM wallet_transactions WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        return [self._wallet_transaction(row) for row in rows]

    async def list_required_chats(self) -> list[RequiredChat]:
        rows = await self._fetchall("SELECT * FROM required_chats ORDER BY id ASC")
        return [self._required_chat(row) for row in rows]

    async def add_required_chat(self, chat_id: int, title: str, invite_link: str) -> RequiredChat:
        cur = await self.db.execute(
            "INSERT INTO required_chats (chat_id, title, invite_link, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, title, invite_link, utcnow()),
        )
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM required_chats WHERE id = ?", (cur.lastrowid,))
        return self._required_chat(row)

    async def remove_required_chat(self, chat_id: int) -> None:
        await self.db.execute("DELETE FROM required_chats WHERE chat_id = ?", (chat_id,))
        await self.db.commit()

    async def get_trial_enabled(self) -> bool:
        return await self.get_setting(TRIAL_ENABLED_KEY, "0") == "1"

    async def set_trial_enabled(self, enabled: bool) -> None:
        await self.set_setting(TRIAL_ENABLED_KEY, "1" if enabled else "0")

    async def get_trial_traffic_gb(self) -> int:
        try:
            return max(int(await self.get_setting(TRIAL_TRAFFIC_GB_KEY, "1")), 1)
        except ValueError:
            return 1

    async def set_trial_traffic_gb(self, gb: int) -> None:
        await self.set_setting(TRIAL_TRAFFIC_GB_KEY, str(max(gb, 1)))

    async def get_trial_days(self) -> int:
        try:
            return max(int(await self.get_setting(TRIAL_DAYS_KEY, "1")), 1)
        except ValueError:
            return 1

    async def set_trial_days(self, days: int) -> None:
        await self.set_setting(TRIAL_DAYS_KEY, str(max(days, 1)))

    async def has_trial_grant(self, user_id: int) -> bool:
        row = await self._fetchone("SELECT 1 FROM trial_grants WHERE user_id = ?", (user_id,))
        return row is not None

    async def grant_trial(self, user_id: int) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO trial_grants (user_id, granted_at) VALUES (?, ?)",
            (user_id, utcnow()),
        )
        await self.db.commit()

    async def create_ticket(self, user_id: int, subject: str, text: str) -> Ticket:
        now = utcnow()
        cur = await self.db.execute(
            "INSERT INTO tickets (user_id, subject, status, created_at, updated_at) VALUES (?, ?, 'open', ?, ?)",
            (user_id, subject, now, now),
        )
        ticket_id = int(cur.lastrowid)
        await self.db.execute(
            "INSERT INTO ticket_messages (ticket_id, sender_role, text, created_at) VALUES (?, 'buyer', ?, ?)",
            (ticket_id, text, now),
        )
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return self._ticket(row)

    async def get_ticket(self, ticket_id: int) -> Ticket:
        row = await self._fetchone("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return self._ticket(row)

    async def list_user_tickets(self, user_id: int) -> list[Ticket]:
        rows = await self._fetchall("SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC", (user_id,))
        return [self._ticket(row) for row in rows]

    async def list_open_tickets(self, *, limit: int = 20) -> list[Ticket]:
        rows = await self._fetchall(
            "SELECT * FROM tickets WHERE status = 'open' ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [self._ticket(row) for row in rows]

    async def add_ticket_message(self, ticket_id: int, *, sender_role: str, text: str) -> None:
        now = utcnow()
        await self.db.execute(
            "INSERT INTO ticket_messages (ticket_id, sender_role, text, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, sender_role, text, now),
        )
        await self.db.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (now, ticket_id))
        await self.db.commit()

    async def close_ticket(self, ticket_id: int) -> None:
        await self.db.execute(
            "UPDATE tickets SET status = 'closed', updated_at = ? WHERE id = ?",
            (utcnow(), ticket_id),
        )
        await self.db.commit()

    async def list_ticket_messages(self, ticket_id: int) -> list[TicketMessage]:
        rows = await self._fetchall(
            "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY id ASC",
            (ticket_id,),
        )
        return [self._ticket_message(row) for row in rows]

    async def list_discount_codes(self) -> list[DiscountCode]:
        rows = await self._fetchall("SELECT * FROM discount_codes ORDER BY id DESC")
        return [self._discount_code(row) for row in rows]

    async def create_discount_code(self, code: str, discount_percent: int, *, max_uses: int = 0) -> DiscountCode:
        normalized = code.strip().lower()
        cur = await self.db.execute(
            """
            INSERT INTO discount_codes (code, discount_percent, max_uses, used_count, active, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, 0, 1, NULL, ?, ?)
            """,
            (normalized, discount_percent, max_uses, utcnow(), utcnow()),
        )
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM discount_codes WHERE id = ?", (cur.lastrowid,))
        return self._discount_code(row)

    async def get_discount_code(self, code: str) -> DiscountCode | None:
        row = await self._fetchone("SELECT * FROM discount_codes WHERE code = ? AND active = 1", (code.strip().lower(),))
        return self._discount_code(row) if row else None

    async def apply_discount_code(self, code_id: int) -> bool:
        cur = await self.db.execute(
            """
            UPDATE discount_codes
            SET used_count = used_count + 1, updated_at = ?
            WHERE id = ? AND active = 1
              AND (max_uses = 0 OR used_count < max_uses)
            """,
            (utcnow(), code_id),
        )
        await self.db.commit()
        return cur.rowcount > 0

    async def sales_report(self, *, days: int) -> SalesReport:
        since = utcnow()  # simplified: use all time for MVP if date parsing heavy
        _ = since
        sub_row = await self._fetchone(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(final_price), 0) AS total FROM subscriptions",
        )
        pay_row = await self._fetchone(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(requested_amount), 0) AS total
            FROM payments WHERE status = 'approved'
            """,
        )
        return SalesReport(
            subscription_count=int(sub_row["cnt"]) if sub_row else 0,
            subscription_revenue=int(sub_row["total"]) if sub_row else 0,
            wallet_charges=int(pay_row["cnt"]) if pay_row else 0,
            wallet_charge_total=int(pay_row["total"]) if pay_row else 0,
        )

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self._fetchone("SELECT value FROM bot_settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.db.execute(
            """
            INSERT INTO bot_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, utcnow()),
        )
        await self.db.commit()

    async def get_support_username(self) -> str:
        return await self.get_setting(SUPPORT_USERNAME_KEY, "")

    async def set_support_username(self, username: str) -> str:
        normalized = normalize_support_username(username)
        if not normalized:
            raise ValueError("invalid_support_username")
        await self.set_setting(SUPPORT_USERNAME_KEY, normalized)
        return normalized

    async def get_earning_enabled(self) -> bool:
        return await self.get_setting(EARNING_ENABLED_KEY, "0") == "1"

    async def set_earning_enabled(self, enabled: bool) -> None:
        await self.set_setting(EARNING_ENABLED_KEY, "1" if enabled else "0")

    async def get_earning_percent(self) -> int:
        try:
            percent = int(await self.get_setting(EARNING_PERCENT_KEY, "0"))
        except ValueError:
            return 0
        return min(max(percent, 0), 100)

    async def set_earning_percent(self, percent: int) -> None:
        if percent < 0 or percent > 100:
            raise ValueError("invalid_earning_percent")
        await self.set_setting(EARNING_PERCENT_KEY, str(percent))

    async def get_referral_earnings_total(self, user_id: int) -> int:
        row = await self._fetchone(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM wallet_transactions WHERE user_id = ? AND reason = 'referral_commission'",
            (user_id,),
        )
        return int(row["total"])

    async def get_pricing_settings(self) -> PricingSettings:
        row = await self._fetchone("SELECT * FROM pricing_settings WHERE id = 1")
        if not row:
            await self.db.execute(
                """
                INSERT INTO pricing_settings
                    (id, per_gb_price, three_month_extra_price, one_month_enabled, three_month_enabled, updated_at)
                VALUES (1, 0, 0, 1, 1, ?)
                """,
                (utcnow(),),
            )
            await self.db.commit()
            row = await self._fetchone("SELECT * FROM pricing_settings WHERE id = 1")
        return self._pricing_settings(row)

    async def update_pricing_settings(
        self,
        per_gb_price: int | None = None,
        three_month_extra_price: int | None = None,
        one_month_enabled: bool | None = None,
        three_month_enabled: bool | None = None,
    ) -> PricingSettings:
        current = await self.get_pricing_settings()
        values = (
            current.per_gb_price if per_gb_price is None else per_gb_price,
            current.three_month_extra_price if three_month_extra_price is None else three_month_extra_price,
            int(current.one_month_enabled if one_month_enabled is None else one_month_enabled),
            int(current.three_month_enabled if three_month_enabled is None else three_month_enabled),
            utcnow(),
        )
        await self.db.execute(
            """
            UPDATE pricing_settings
            SET per_gb_price = ?, three_month_extra_price = ?, one_month_enabled = ?, three_month_enabled = ?, updated_at = ?
            WHERE id = 1
            """,
            values,
        )
        await self.db.commit()
        return await self.get_pricing_settings()

    async def list_traffic_presets(self) -> list[TrafficPreset]:
        rows = await self._fetchall("SELECT * FROM traffic_presets ORDER BY gb ASC")
        return [self._traffic_preset(row) for row in rows]

    async def get_traffic_preset(self, gb: int) -> TrafficPreset | None:
        row = await self._fetchone("SELECT * FROM traffic_presets WHERE gb = ?", (gb,))
        return self._traffic_preset(row) if row else None

    async def update_preset_discount(self, gb: int, discount_percent: int) -> TrafficPreset | None:
        cur = await self.db.execute(
            "UPDATE traffic_presets SET discount_percent = ?, updated_at = ? WHERE gb = ?",
            (discount_percent, utcnow(), gb),
        )
        await self.db.commit()
        if cur.rowcount == 0:
            return None
        return await self.get_traffic_preset(gb)

    def build_offer(self, settings: PricingSettings, traffic_gb: int, duration_days: int, source: str, discount_percent: int = 0) -> PurchaseOffer:
        if source == "trial":
            if traffic_gb < 1:
                raise ValueError("invalid_traffic")
            return PurchaseOffer(traffic_gb, max(duration_days, 1), source, 100, 0, 0, 0)
        if traffic_gb < 1 or traffic_gb > 200:
            raise ValueError("invalid_traffic")
        if duration_days == 30:
            if not settings.one_month_enabled:
                raise ValueError("duration_disabled")
            duration_extra = 0
        elif duration_days == 90:
            if not settings.three_month_enabled:
                raise ValueError("duration_disabled")
            duration_extra = settings.three_month_extra_price
        else:
            raise ValueError("invalid_duration")
        if source == "manual":
            discount_percent = 0
        if discount_percent < 0 or discount_percent > 100:
            raise ValueError("invalid_discount")
        base_price = traffic_gb * settings.per_gb_price
        before_discount = base_price + duration_extra
        final_price = before_discount * (100 - discount_percent) // 100
        return PurchaseOffer(traffic_gb, duration_days, source, discount_percent, base_price, duration_extra, final_price)

    async def create_subscription_after_charge(
        self,
        user: User,
        offer: PurchaseOffer,
        marzban_username: str,
        subscription_url: str,
        expires_at: str,
    ) -> Subscription:
        if user.wallet_balance < offer.final_price:
            raise ValueError("insufficient_balance")
        cur = await self.db.execute(
            """
            INSERT INTO subscriptions (
                user_id, plan_id, marzban_username, subscription_url, expires_at, traffic_gb,
                duration_days, discount_percent, base_price, duration_extra, final_price, purchase_source,
                status, created_at, updated_at
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                user.id,
                marzban_username,
                subscription_url,
                expires_at,
                offer.traffic_gb,
                offer.duration_days,
                offer.discount_percent,
                offer.base_price,
                offer.duration_extra,
                offer.final_price,
                offer.source,
                utcnow(),
                utcnow(),
            ),
        )
        subscription_id = cur.lastrowid
        await self.adjust_wallet(user.id, -offer.final_price, "subscription_purchase", linked_subscription_id=subscription_id)
        if await self.get_earning_enabled() and user.referred_by:
            earning_percent = await self.get_earning_percent()
            commission = offer.final_price * earning_percent // 100
            if commission > 0:
                await self.adjust_wallet(user.referred_by, commission, "referral_commission", linked_subscription_id=subscription_id)
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
        return self._subscription(row)

    async def list_user_subscriptions(self, user_id: int) -> list[Subscription]:
        rows = await self._fetchall("SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id DESC", (user_id,))
        return [self._subscription(row) for row in rows]

    async def count_user_subscriptions(self, user_id: int) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS count FROM subscriptions WHERE user_id = ?", (user_id,))
        return int(row["count"])

    async def active_subscription_traffic_gb(self) -> int:
        row = await self._fetchone("SELECT COALESCE(SUM(traffic_gb), 0) AS total FROM subscriptions WHERE status = 'active'")
        return int(row["total"] or 0)

    async def list_user_subscriptions_page(self, user_id: int, page: int, per_page: int = 10) -> list[Subscription]:
        offset = max(page - 1, 0) * per_page
        rows = await self._fetchall(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, per_page, offset),
        )
        return [self._subscription(row) for row in rows]

    async def get_user_subscription(self, user_id: int, subscription_id: int) -> Subscription | None:
        row = await self._fetchone(
            "SELECT * FROM subscriptions WHERE id = ? AND user_id = ?",
            (subscription_id, user_id),
        )
        return self._subscription(row) if row else None

    async def update_subscription_url(self, subscription_id: int, subscription_url: str) -> Subscription:
        await self.db.execute(
            "UPDATE subscriptions SET subscription_url = ?, updated_at = ? WHERE id = ?",
            (subscription_url, utcnow(), subscription_id),
        )
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
        return self._subscription(row)

    async def extend_subscription_after_charge(
        self,
        user: User,
        subscription: Subscription,
        offer: PurchaseOffer,
        expires_at: str,
    ) -> Subscription:
        if user.wallet_balance < offer.final_price:
            raise ValueError("insufficient_balance")
        await self.db.execute(
            """
            UPDATE subscriptions
            SET expires_at = ?,
                traffic_gb = traffic_gb + ?,
                duration_days = duration_days + ?,
                final_price = final_price + ?,
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (expires_at, offer.traffic_gb, offer.duration_days, offer.final_price, utcnow(), subscription.id, user.id),
        )
        await self.adjust_wallet(user.id, -offer.final_price, "subscription_extend", linked_subscription_id=subscription.id)
        await self.db.commit()
        row = await self._fetchone("SELECT * FROM subscriptions WHERE id = ?", (subscription.id,))
        return self._subscription(row)

    async def _fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        async with self.db.execute(sql, params) as cur:
            return await cur.fetchone()

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with self.db.execute(sql, params) as cur:
            return await cur.fetchall()

    def _user(self, row: aiosqlite.Row) -> User:
        keys = row.keys()
        is_blocked = bool(row["is_blocked"]) if "is_blocked" in keys else False
        first_name = row["first_name"] if "first_name" in keys else None
        last_name = row["last_name"] if "last_name" in keys else None
        username = row["username"] if "username" in keys else None
        return User(
            row["id"],
            row["telegram_id"],
            row["role"],
            row["wallet_balance"],
            row["referral_code"],
            row["referred_by"],
            is_blocked,
            first_name,
            last_name,
            username,
        )

    def _pricing_settings(self, row: aiosqlite.Row) -> PricingSettings:
        return PricingSettings(row["per_gb_price"], row["three_month_extra_price"], bool(row["one_month_enabled"]), bool(row["three_month_enabled"]))

    def _traffic_preset(self, row: aiosqlite.Row) -> TrafficPreset:
        return TrafficPreset(row["id"], row["gb"], row["discount_percent"], bool(row["active"]))

    def _payment(self, row: aiosqlite.Row) -> Payment:
        keys = row.keys()
        created_at = row["created_at"] if "created_at" in keys else ""
        return Payment(row["id"], row["user_id"], row["requested_amount"], row["screenshot_file_id"], row["status"], created_at)

    def _wallet_transaction(self, row: aiosqlite.Row) -> WalletTransaction:
        return WalletTransaction(row["id"], row["user_id"], row["amount"], row["reason"], row["created_at"])

    def _required_chat(self, row: aiosqlite.Row) -> RequiredChat:
        return RequiredChat(row["id"], row["chat_id"], row["title"], row["invite_link"])

    def _pending_payment_view(self, row: aiosqlite.Row) -> PendingPaymentView:
        user = User(
            row["u_id"],
            row["telegram_id"],
            row["role"],
            row["wallet_balance"],
            row["referral_code"],
            row["referred_by"],
            bool(row["is_blocked"]),
            row["first_name"],
            row["last_name"],
            row["username"],
        )
        return PendingPaymentView(self._payment(row), user)

    def _ticket(self, row: aiosqlite.Row) -> Ticket:
        return Ticket(row["id"], row["user_id"], row["subject"], row["status"], row["created_at"], row["updated_at"])

    def _ticket_message(self, row: aiosqlite.Row) -> TicketMessage:
        return TicketMessage(row["id"], row["ticket_id"], row["sender_role"], row["text"], row["created_at"])

    def _discount_code(self, row: aiosqlite.Row) -> DiscountCode:
        return DiscountCode(
            row["id"],
            row["code"],
            row["discount_percent"],
            row["max_uses"],
            row["used_count"],
            bool(row["active"]),
            row["expires_at"],
        )

    def _subscription(self, row: aiosqlite.Row) -> Subscription:
        return Subscription(
            row["id"],
            row["user_id"],
            row["plan_id"],
            row["marzban_username"],
            row["subscription_url"],
            row["expires_at"],
            row["traffic_gb"],
            row["duration_days"],
            row["discount_percent"],
            row["base_price"],
            row["duration_extra"],
            row["final_price"],
            row["purchase_source"],
            row["status"],
        )


DEFAULT_PRESET_GB = (5, 10, 15, 20, 50, 75, 100)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'buyer')),
    wallet_balance INTEGER NOT NULL DEFAULT 0,
    referral_code TEXT NOT NULL UNIQUE,
    referred_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price >= 0),
    duration_days INTEGER NOT NULL CHECK (duration_days > 0),
    traffic_gb INTEGER NOT NULL CHECK (traffic_gb > 0),
    marzban_settings TEXT NOT NULL DEFAULT '{}',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    requested_amount INTEGER NOT NULL CHECK (requested_amount > 0),
    screenshot_file_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'declined')),
    reviewed_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    plan_id INTEGER REFERENCES plans(id),
    marzban_username TEXT NOT NULL,
    subscription_url TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    traffic_gb INTEGER NOT NULL,
    duration_days INTEGER NOT NULL DEFAULT 30,
    discount_percent INTEGER NOT NULL DEFAULT 0,
    base_price INTEGER NOT NULL DEFAULT 0,
    duration_extra INTEGER NOT NULL DEFAULT 0,
    final_price INTEGER NOT NULL DEFAULT 0,
    purchase_source TEXT NOT NULL DEFAULT 'legacy',
    status TEXT NOT NULL CHECK (status IN ('active', 'expired', 'disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pricing_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    per_gb_price INTEGER NOT NULL DEFAULT 0 CHECK (per_gb_price >= 0),
    three_month_extra_price INTEGER NOT NULL DEFAULT 0 CHECK (three_month_extra_price >= 0),
    one_month_enabled INTEGER NOT NULL DEFAULT 1,
    three_month_enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gb INTEGER NOT NULL UNIQUE CHECK (gb > 0),
    discount_percent INTEGER NOT NULL DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent <= 100),
    active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    linked_payment_id INTEGER REFERENCES payments(id),
    linked_subscription_id INTEGER REFERENCES subscriptions(id),
    created_at TEXT NOT NULL
);
"""
