import functools
import logging
import random
import string
from pathlib import Path

from .bottle import hook, post, request, response, run, route, static_file

from . import DATA_DIR, exceptions
from .models import ChaoxingUser
from .utils import geanerate_sid, check_sid_format


_ret_code = {
    0: "OK",
    1: "invalid token",
    2: "username or password error",
    3: "invalid request message",
    -1: "unknown error"
}
logger = logging.getLogger(__name__)
web_root = (Path(__file__).parent / Path("webroot")).resolve()


def setup_logging(level=logging.ERROR):
    root = logging.getLogger()
    root.addHandler(logging.StreamHandler())
    root.setLevel(level)


def make_response(ret_code, extra_message=None, body=None):
    message = _ret_code[ret_code]
    if extra_message:
        message += "," + extra_message
    result = {
        "ret": ret_code,
        "message": message
    }
    if body:
        result.update(body)
    return result


def login_required(func):
    """login_required 装饰器，对需要登录的路由使用可在 request 对象中增加属性：user,
    并保证 user 可用。
    """
    @functools.wraps(func)
    def wrap(*vargs, **kwargs):
        sid = request.get_cookie("sid")
        ret = 1
        message = ""
        logger.debug("start check sid...")
        if check_sid_format(sid):
            file = DATA_DIR / Path(sid)
            if file.exists():
                request.sid = sid
                user: ChaoxingUser = ChaoxingUser.load_from(file)
                if not user.is_login:
                    logger.debug("login...")
                    try:
                        user.login()
                        request.user = user
                        return func(*vargs, **kwargs)
                    except exceptions.PasswordError:
                        ret = 2
                    except exceptions.LoginFailedError as e:
                        ret = -1
                        message = str(e)
                else:
                    request.user = user
                    return func(*vargs, **kwargs)
            else:
                logger.debug("token not exists")
        else:
            logger.debug("token format error")
        
        logger.debug("check sid end")
        return make_response(ret, message)
    return wrap


def json_required(func):
    """josn_required 装饰器：如果 content-type 不是 application/json, 直接返回失败。
    如果请求体格式实际不是 json, 也会返回失败。
    """
    @functools.wraps(func)
    def wrap(*vargs, **kwargs):
        ret = 3
        message = ""
        try:
            tmp = request.json
            if tmp is None:
                logger.debug("request message is None")
            return func(*vargs, **kwargs)
        except ValueError as e:
            message = str(e)
        return make_response(ret, message)
    return wrap


@hook("after_request")
def after_request():
    if hasattr(request, "user"):
        user = request.user
        user.dump_to()
        logger.debug(f"save user object to local drive success.")


@post("/api/login")
@json_required
def login():
    ret = -1
    message = ""
    try:
        payload = request.json
        username = payload["username"] #pylint: disable=unsubscriptable-object
        password = payload["password"] #pylint: disable=unsubscriptable-object
        message = ""
    except KeyError as e:
        username = password = None
        message = f"错误：{e.args}"
    print(f"login: {username} - {password}")
    if username and password and len(username) == 8:
        user = ChaoxingUser(username, password)
        try:
            user.login()
            # 随机序列
            randstr = geanerate_sid()
            file = DATA_DIR / Path(randstr)
            user.dump_to(file)
            response.set_cookie("sid", randstr, max_age=100 * 24 * 60 * 60)
            return make_response(0)
        except exceptions.PasswordError:
            ret = 2
        except exceptions.LoginFailedError as e:
            message = str(e)
    else:
        ret = 2
    return make_response(ret, message)


@post("/api/check_sid")
@json_required
def check_sid():
    sid = request.get_cookie("sid")
    ret = 0
    result = { 
        "ret": ret, 
        "message": _ret_code[ret],
        "sid_available": True
    }
    if check_sid_format(sid):
        file = DATA_DIR / Path(sid)
        if file.exists():
            return result
        else:
            logger.debug("sid not exists")
    else:
        logger.debug("invalid sid format.")
    result["sid_available"] = False
    return result


@post("/api/get_unfinish_works")
@login_required
@json_required
def get_unfinish_works():
    disable_cache = False
    if request.json and ("disable_cache" in request.json.keys()): #pylint: disable=no-member
        disable_cache = request.json["disable_cache"] #pylint: disable=unsubscriptable-object
    user = request.user
    course_list = user.get_unfinish_work_list(disable_cache=disable_cache)
    result = {"ret": 0}
    data = []
    for course, works in course_list:
        for w in works:
            deadline = w.endTime
            if deadline is None:
                deadline = -1
            else:
                deadline = deadline.timestamp()
            data.append({
                "courseName": course.courseName,
                "workName": w.workName,
                "deadline": deadline
            })
    data.sort(key=lambda x: x["deadline"])
    result["data"] = data
    result["update_at"] = user.last_update_time
    return result


@post("/api/logout")
def logout():
    if hasattr(request, "sid"):
        sid = request.sid
        file = DATA_DIR / Path(sid)
        file.unlink()
        del request.sid
        del request.user
        logger.debug(f"file {file} deleted.")
    response.set_cookie("sid", "")
    return {
        "ret": 0,
        "message": _ret_code[0]
    }


# static file
@route("/")
def home():
    logger.debug(f"webroot: {web_root}")
    return static_file("index.html", root=web_root)


@route("/<filename>")
def resource_file(filename):
    return static_file(filename, root=web_root)


@route("/static/<filepath:path>")
def resource_file2(filepath):
    return static_file(filepath, root=(web_root / Path("static")))


def main(host="localhost", port=5986):
    setup_logging(level=logging.DEBUG)
    run(host=host, port=port)


if __name__ == "__main__":
    main()
