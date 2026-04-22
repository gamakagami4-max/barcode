# server/repositories/muser_repo.py

from datetime import datetime
from server.db import get_connection
import hashlib


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    """SHA-256 hash for password storage. Replace with bcrypt in production."""
    return hashlib.sha256(plain.encode()).hexdigest()


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_muser() -> list[dict]:
    sql = """
        SELECT
            usrcod  AS pk,
            usrdsc  AS description,
            usflag  AS flag,
            uspath  AS path,
            usalbr  AS al_br,
            uscono  AS company_no
        FROM barcodesap.muser
        ORDER BY usrcod
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_muser_by_pk(pk: str) -> dict | None:
    sql = """
        SELECT
            usrcod  AS pk,
            usrdsc  AS description,
            usflag  AS flag,
            uspath  AS path,
            usalbr  AS al_br,
            uscono  AS company_no
        FROM barcodesap.muser
        WHERE usrcod = %s
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (pk,))
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


# ── Authentication ────────────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> dict | None:
    """
    Verify username + password.
    Returns the user dict (without password) on success, None on failure.
    Only active users (usflag = 1) are allowed to log in.
    """
    sql = """
        SELECT
            usrcod  AS pk,
            usrdsc  AS description,
            usrpwd  AS password_hash,
            usflag  AS flag,
            uspath  AS path,
            usalbr  AS al_br,
            uscono  AS company_no
        FROM barcodesap.muser
        WHERE usrcod = %s
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (username,))
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        if row is None:
            return None

        user = dict(zip(cols, row))

        # Check active flag
        if user.get("flag") != 1:
            return None

        # Verify password
        if user["password_hash"] != _hash_password(password):
            return None

        # Strip password from returned dict
        user.pop("password_hash", None)
        return user
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_muser(
    usrcod: str,
    usrdsc: str | None = None,
    password: str | None = None,
    flag: int = 1,
    path: str | None = None,
    al_br: int | None = None,
    company_no: str | None = None,
) -> str:
    """
    Insert a new muser row.
    PK is usrcod (varchar 20), supplied by the caller.
    Password is stored as SHA-256 hash.
    """
    hashed_pwd = _hash_password(password) if password else None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.muser (
                usrcod,
                usrdsc,
                usrpwd,
                usflag,
                uspath,
                usalbr,
                uscono
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING usrcod
            """,
            (usrcod, usrdsc, hashed_pwd, flag, path, al_br, company_no),
        )
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update ────────────────────────────────────────────────────────────────────

def update_muser(
    pk: str,
    usrdsc: str | None,
    flag: int | None,
    path: str | None,
    al_br: int | None,
    company_no: str | None,
) -> None:
    """
    Update editable fields on an existing muser row.
    Password is NOT updated here — use change_password() instead.
    usrcod (PK) is intentionally not updatable.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.muser
            SET
                usrdsc = %s,
                usflag = %s,
                uspath = %s,
                usalbr = %s,
                uscono = %s
            WHERE usrcod = %s
            """,
            (usrdsc, flag, path, al_br, company_no, pk),
        )
        if cur.rowcount == 0:
            raise Exception(f"User '{pk}' not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Change Password ───────────────────────────────────────────────────────────

def change_password(pk: str, old_password: str, new_password: str) -> None:
    """
    Change a user's password after verifying the old one.
    Raises Exception on wrong old password or user not found.
    """
    sql = "SELECT usrpwd FROM barcodesap.muser WHERE usrcod = %s"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (pk,))
        row = cur.fetchone()
        if row is None:
            raise Exception(f"User '{pk}' not found.")
        if row[0] != _hash_password(old_password):
            raise Exception("Incorrect current password.")
        cur.execute(
            "UPDATE barcodesap.muser SET usrpwd = %s WHERE usrcod = %s",
            (_hash_password(new_password), pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_password(pk: str, new_password: str) -> None:
    """
    Admin-level password reset — no old password required.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE barcodesap.muser SET usrpwd = %s WHERE usrcod = %s",
            (_hash_password(new_password), pk),
        )
        if cur.rowcount == 0:
            raise Exception(f"User '{pk}' not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_muser(pk: str) -> None:
    """
    Hard delete — use only if no FK constraints prevent it.
    Consider setting usflag = 0 to deactivate instead.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM barcodesap.muser WHERE usrcod = %s", (pk,))
        if cur.rowcount == 0:
            raise Exception(f"User '{pk}' not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deactivate_muser(pk: str) -> None:
    """
    Soft deactivation — sets usflag = 0, blocking login without deleting data.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE barcodesap.muser SET usflag = 0 WHERE usrcod = %s", (pk,)
        )
        if cur.rowcount == 0:
            raise Exception(f"User '{pk}' not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()