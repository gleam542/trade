"""Basic 認證比對的檢查：`python test_auth.py`，不需要資料庫或伺服器。

曾經出過的 bug：secrets.compare_digest 收到 str 時只接受 ASCII，密碼是中文、
或有人在登入框打了中文，就會丟 TypeError 讓伺服器回 500。
"""

import base64

import api


def _header(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def _with_password(pw: str, user: str = "trade"):
    api._AUTH_PASSWORD, api._AUTH_USER = pw, user


def test_non_ascii_password_correct():
    _with_password("新密碼")
    assert api._credentials_ok(_header("trade", "新密碼"))


def test_non_ascii_password_wrong():
    _with_password("新密碼")
    assert not api._credentials_ok(_header("trade", "舊密碼"))


def test_non_ascii_input_against_ascii_password():
    # 有人在登入框打中文，不該讓伺服器 500，應該單純判定失敗
    _with_password("Kx9mR2vLq")
    assert not api._credentials_ok(_header("管理員", "隨便打"))


def test_ascii_still_works():
    _with_password("Kx9mR2vLq")
    assert api._credentials_ok(_header("trade", "Kx9mR2vLq"))
    assert not api._credentials_ok(_header("trade", "wrong"))
    assert not api._credentials_ok(_header("nobody", "Kx9mR2vLq"))


def test_malformed_header():
    _with_password("Kx9mR2vLq")
    assert not api._credentials_ok(None)
    assert not api._credentials_ok("Bearer abc")
    assert not api._credentials_ok("Basic !!!notbase64")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✓ {name}")
    print("\n全部通過")
