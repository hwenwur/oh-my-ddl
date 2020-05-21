class PasswordError(ValueError):
    """学号或密码错误
    """
    pass


class LoginFailedError(RuntimeError):
    """登录失败
    """
    pass


class TryTooManyError(RuntimeError):
    """登录尝试次数过多
    """
    pass
