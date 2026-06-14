"""
用户认证数据管理 —— SQLite 持久化用户注册/登录数据。

所有配置通过构造参数注入，遵循 app/common/rag_manager.py 的风格。
密码使用 PBKDF2-SHA256 + 随机盐存储，不依赖第三方密码库。
"""

import os
import hashlib
import secrets
import sqlite3

from app.common.logger import logger


def _hash_password(password: str) -> str:
    """PBKDF2-SHA256 + 随机盐，返回 'salt:hash_hex' 格式字符串。"""
    salt = secrets.token_hex(16)
    iterations = 600_000
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"{salt}:{key.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """验证密码是否匹配已存储的哈希。"""
    try:
        salt, key_hex = stored.split(":", 1)
        iterations = 600_000
        new_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return secrets.compare_digest(new_key.hex(), key_hex)
    except (ValueError, AttributeError):
        return False


class UserManager:
    """用户认证数据管理器（SQLite）。

    Attributes:
        db_path: SQLite 数据库文件路径。
        connection: pymysqlite 连接实例。
    """

    def __init__(self, db_path: str):
        """
        Args:
            db_path: users.db 文件的完整路径。
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_table()
        logger.info(f"用户数据库已就绪: {db_path}")

    def _init_table(self):
        """创建用户表（如果不存在）。"""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    UNIQUE NOT NULL,
                password_hash TEXT  NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self.connection.commit()

    # ── 用户管理 ───────────────────────────────────────

    def create_user(self, username: str, password: str) -> dict | None:
        """注册新用户。

        Args:
            username: 用户名。
            password: 明文密码。

        Returns:
            成功返回用户信息 dict，用户名已存在返回 None。
        """
        try:
            hash_value = _hash_password(password)
            cursor = self.connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username.strip(), hash_value),
            )
            self.connection.commit()
            user = {
                "id": cursor.lastrowid,
                "username": username.strip(),
                "created_at": None,
            }
            logger.info(f"新用户注册: {username.strip()}")
            return user
        except sqlite3.IntegrityError:
            logger.warning(f"用户名已存在: {username}")
            return None

    def authenticate(self, username: str, password: str) -> dict | None:
        """验证用户名密码。

        Args:
            username: 用户名。
            password: 明文密码。

        Returns:
            成功返回用户信息 dict，失败返回 None。
        """
        row = self.connection.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()

        if row is None:
            return None

        if not _verify_password(password, row["password_hash"]):
            return None

        return {
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
        }

    def get_by_id(self, user_id: int) -> dict | None:
        """按 ID 查询用户。

        Args:
            user_id: 用户 ID。

        Returns:
            用户信息 dict 或 None。
        """
        row = self.connection.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
        }

    # ── 资源释放 ──────────────────────────────────────

    def close(self):
        """关闭数据库连接。"""
        try:
            self.connection.close()
            logger.info("用户数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭用户数据库连接时出错: {e}")
