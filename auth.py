#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""已认证服务号网页授权与 PC 扫码登录桥接。"""
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

from database import connect, load_dotenv


load_dotenv()
TICKET_TTL_SECONDS = int(os.environ.get("AUTH_TICKET_TTL", "300"))
SESSION_TTL_SECONDS = int(os.environ.get("AUTH_SESSION_TTL", str(30 * 24 * 60 * 60)))

SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_wechat_users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    openid VARCHAR(128) NOT NULL,
    unionid VARCHAR(128) NOT NULL DEFAULT '',
    nickname VARCHAR(255) NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_auth_wechat_openid (openid),
    INDEX idx_auth_wechat_unionid (unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_login_tickets (
    ticket VARCHAR(64) NOT NULL PRIMARY KEY,
    oauth_state VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    authorized_at TIMESTAMP NULL,
    consumed_at TIMESTAMP NULL,
    UNIQUE KEY uk_auth_login_state (oauth_state),
    INDEX idx_auth_login_expiry (expires_at),
    CONSTRAINT fk_auth_ticket_user FOREIGN KEY (user_id)
        REFERENCES auth_wechat_users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash CHAR(64) NOT NULL PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    INDEX idx_auth_session_expiry (expires_at),
    INDEX idx_auth_session_user (user_id),
    CONSTRAINT fk_auth_session_user FOREIGN KEY (user_id)
        REFERENCES auth_wechat_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def _config():
    app_id = os.environ.get("WECHAT_APP_ID", "").strip()
    app_secret = os.environ.get("WECHAT_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise RuntimeError("微信登录尚未配置")
    return app_id, app_secret


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _public_user(row):
    return {
        "id": row["id"],
        "nickname": row["nickname"] or "微信用户",
        "avatar_url": row["avatar_url"] or "",
    }


def init_auth_schema():
    with connect() as connection:
        with connection.cursor() as cursor:
            for statement in SCHEMA.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
        connection.commit()


def create_login_ticket(base_url):
    app_id, _ = _config()
    ticket = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(32)
    callback = "%s/api/auth/wechat/callback?ticket=%s" % (
        base_url.rstrip("/"),
        urllib.parse.quote(ticket, safe=""),
    )
    params = urllib.parse.urlencode({
        "appid": app_id,
        "redirect_uri": callback,
        "response_type": "code",
        "scope": "snsapi_userinfo",
        "state": state,
    })
    authorize_url = (
        "https://open.weixin.qq.com/connect/oauth2/authorize?"
        + params
        + "#wechat_redirect"
    )
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM auth_login_tickets WHERE expires_at <= UTC_TIMESTAMP()"
            )
            cursor.execute(
                "DELETE FROM auth_sessions WHERE expires_at <= UTC_TIMESTAMP()"
            )
            cursor.execute(
                """
                INSERT INTO auth_login_tickets
                    (ticket, oauth_state, expires_at)
                VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND))
                """,
                (ticket, state, TICKET_TTL_SECONDS),
            )
        connection.commit()
    return {
        "ticket": ticket,
        "authorize_url": authorize_url,
        "expires_in": TICKET_TTL_SECONDS,
    }


def _wechat_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "investment-news/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError("微信接口请求失败（HTTP %d）" % error.code) from None
    except urllib.error.URLError:
        raise RuntimeError("暂时无法连接微信授权服务") from None
    if payload.get("errcode"):
        raise RuntimeError(
            "微信接口返回错误 %s：%s"
            % (payload.get("errcode"), payload.get("errmsg", "未知错误"))
        )
    return payload


def authorize_callback(ticket, state, code):
    app_id, app_secret = _config()
    if not ticket or not state or not code:
        raise ValueError("微信授权参数不完整")

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ticket, oauth_state, status
                FROM auth_login_tickets
                WHERE ticket = %s AND expires_at > UTC_TIMESTAMP()
                FOR UPDATE
                """,
                (ticket,),
            )
            row = cursor.fetchone()
            if not row or row["status"] != "pending":
                raise ValueError("登录二维码已失效或已使用")
            if not secrets.compare_digest(row["oauth_state"], state):
                raise ValueError("微信授权状态校验失败")
        connection.rollback()

    token_url = "https://api.weixin.qq.com/sns/oauth2/access_token?" + urllib.parse.urlencode({
        "appid": app_id,
        "secret": app_secret,
        "code": code,
        "grant_type": "authorization_code",
    })
    token_data = _wechat_json(token_url)
    access_token = token_data.get("access_token", "")
    openid = token_data.get("openid", "")
    if not access_token or not openid:
        raise RuntimeError("微信授权结果缺少用户标识")

    user_url = "https://api.weixin.qq.com/sns/userinfo?" + urllib.parse.urlencode({
        "access_token": access_token,
        "openid": openid,
        "lang": "zh_CN",
    })
    profile = _wechat_json(user_url)
    nickname = str(profile.get("nickname") or "微信用户")[:255]
    avatar_url = str(profile.get("headimgurl") or "")
    unionid = str(profile.get("unionid") or "")[:128]

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO auth_wechat_users
                    (openid, unionid, nickname, avatar_url)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    unionid = VALUES(unionid),
                    nickname = VALUES(nickname),
                    avatar_url = VALUES(avatar_url),
                    last_login_at = CURRENT_TIMESTAMP
                """,
                (openid, unionid, nickname, avatar_url),
            )
            cursor.execute(
                "SELECT id FROM auth_wechat_users WHERE openid = %s",
                (openid,),
            )
            user_id = cursor.fetchone()["id"]
            cursor.execute(
                """
                UPDATE auth_login_tickets
                SET status = 'authorized', user_id = %s,
                    authorized_at = CURRENT_TIMESTAMP
                WHERE ticket = %s AND oauth_state = %s
                  AND status = 'pending' AND expires_at > UTC_TIMESTAMP()
                """,
                (user_id, ticket, state),
            )
            if cursor.rowcount != 1:
                raise ValueError("登录二维码已失效或已使用")
        connection.commit()


def poll_login_ticket(ticket):
    if not ticket:
        raise ValueError("缺少登录票据")
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.status, t.user_id, u.id, u.nickname, u.avatar_url
                FROM auth_login_tickets t
                LEFT JOIN auth_wechat_users u ON u.id = t.user_id
                WHERE t.ticket = %s AND t.expires_at > UTC_TIMESTAMP()
                FOR UPDATE
                """,
                (ticket,),
            )
            row = cursor.fetchone()
            if not row:
                return {"status": "expired"}
            if row["status"] == "pending":
                connection.rollback()
                return {"status": "pending"}
            if row["status"] != "authorized" or not row["user_id"]:
                connection.rollback()
                return {"status": "expired"}

            session_token = secrets.token_urlsafe(48)
            cursor.execute(
                """
                INSERT INTO auth_sessions (token_hash, user_id, expires_at)
                VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND))
                """,
                (_token_hash(session_token), row["user_id"], SESSION_TTL_SECONDS),
            )
            cursor.execute(
                """
                UPDATE auth_login_tickets
                SET status = 'consumed', consumed_at = CURRENT_TIMESTAMP
                WHERE ticket = %s AND status = 'authorized'
                """,
                (ticket,),
            )
        connection.commit()
    return {
        "status": "authorized",
        "session_token": session_token,
        "session_expires_in": SESSION_TTL_SECONDS,
        "user": _public_user(row),
    }


def current_user(session_token):
    if not session_token:
        return None
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.nickname, u.avatar_url
                FROM auth_sessions s
                JOIN auth_wechat_users u ON u.id = s.user_id
                WHERE s.token_hash = %s AND s.expires_at > UTC_TIMESTAMP()
                """,
                (_token_hash(session_token),),
            )
            row = cursor.fetchone()
    return _public_user(row) if row else None


def delete_session(session_token):
    if not session_token:
        return
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM auth_sessions WHERE token_hash = %s",
                (_token_hash(session_token),),
            )
        connection.commit()
