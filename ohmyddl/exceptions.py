class PasswordError(ValueError):
    """学号或密码错误
    """
    pass


class LoginFailedError(RuntimeError):
    """登录失败
    """
    pass
