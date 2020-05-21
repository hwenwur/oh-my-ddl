import functools
import logging
import pickle
import time
import re
from collections import namedtuple
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path

import lxml.etree
import requests

from .exceptions import LoginFailedError, PasswordError, TryTooManyError
from .utils import extract_string, get_params_from_url
from . import __version__
from . import DATA_DIR
from .cachemanager import make_cache_decorator


WorkInfo = namedtuple(
    "WorkInfo",
    [
        "workName", "startTime", "endTime", "workStatus",
        "courseId", "classId", "workRelationId", "workRelationAnswerId", "workReEdit", "enc", "cpi"
    ])
CourseInfo = namedtuple(
    "CourseInfo", ["pageUrl", "courseName", "teacherName", "courseSeq"])

cache = make_cache_decorator(DATA_DIR / Path("cache_data.db"))

#
# def cache_legacy(expire_time):
#     """缓存函数返回值。在expire_time时间内重复调用某个函数（且str(参数)相同）会使用上次的返回值。
#     @expire_time 缓存过期时间，单位：秒。
#
#     例子：\n
#     @cache(60)\n
#     def get_val(x, y, z):
#         # something
#         time.sleep(1)
#         return [x, y, z]
#     如果在60s内，重复调用该函数，并且x,y,z值相同的情况下，会直接使用上次运行的返回值。
#
#     在上述例子中，执行10次get_val(1, 2, 3)只消耗约1秒时间。
#     """
#
#     def decorator(func):
#         @functools.wraps(func)
#         def wrap(self, *vargs, **kwargs):
#             if "disable_cache" in kwargs.keys():
#                 disable_cache = kwargs["disable_cache"]
#             else:
#                 disable_cache = False
#             key = func.__name__
#             for x in vargs:
#                 key += str(x)
#             for x in kwargs.keys():
#                 key += str(x)
#                 key += str(kwargs[x])
#             cache = self._read_cache(key, expire_time=expire_time)
#             if (not disable_cache) and (cache is not None):
#                 self._logger.debug(f"{func.__name__} 使用缓存值。key: {key}")
#                 return cache
#             else:
#                 self._logger.debug(f"call {func.__name__}...")
#                 r = func(self, *vargs, **kwargs)
#                 self._write_cache(key, r)
#                 self.last_update_time = time.time()
#                 return r
#
#         wrap.origin = func
#         return wrap
#
#     return decorator


class ChaoxingUser:
    HTTP_HEADERS = {
        # dummy user-agent
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13) AppleWebKit/603.1.13 (KHTML, like Gecko) '
                      'Version/10.1 Safari/603.1.13',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,"
                  "application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7"
    }
    CACHE_EXPIRE_TIME = 600

    def __init__(self, username, password):
        self.userName = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(self.HTTP_HEADERS)
        self._logger = logging.getLogger(__name__)
        self._cache_table: Dict[str, Tuple[List, float]] = dict()
        # 如果该对象是通过load_from产生的，load_file 为其来源文件，否则 load_from 为空。
        self.load_file = ""
        self.last_update_time = 0
        self.version = __version__

    def http_request(self, url, method, params=None, data=None, referer=None, auto_retry=3) -> requests.models.Response:
        session = self.session
        if referer:
            session.headers.update({
                "Referer": referer
            })
        request = getattr(session, method.lower())
        while True:
            try:
                r = request(url, params=params, data=data)
                return r
            except requests.exceptions.RequestException as e:
                self._logger.error(f"请求时发生错误：{e}")
                if isinstance(e, ValueError):
                    raise
                if auto_retry > 0:
                    time.sleep(1)
                    self._logger.error(f"自动重试: {auto_retry}")
                    auto_retry -= 1
                else:
                    raise

    def http_get(self, url, **kargs):
        return self.http_request(url, "get", **kargs)

    def http_post(self, url, **kargs):
        return self.http_request(url, "post", **kargs)

    def _read_cache(self, key, expire_time=None):
        if key in self._cache_table.keys():
            cached_time = self._cache_table[key][1]
            if expire_time is None:
                expire_time = self.CACHE_EXPIRE_TIME
            if (time.time() - cached_time) < expire_time:
                return self._cache_table[key][0].copy()
        return None

    def _write_cache(self, key, val: list):
        self._cache_table[key] = (val.copy(), time.time())

    @property
    def is_login(self):
        r = self.http_get("http://www.elearning.shu.edu.cn/topjs?index=1")
        if "afterLogin" in r.text:
            return True
        else:
            return False

    def login(self):
        # step 1
        r = self.http_get("http://shu.fysso.chaoxing.com/sso/shu",
                          referer="http://www.elearning.shu.edu.cn/portal")
        if r.url.startswith("http://www.elearning.shu.edu.cn/sso/logind"):
            self._logger.debug("use oauth to login")
        elif r.url == "https://oauth.shu.edu.cn/login":
            # step 2
            self._logger.debug("use username and password to login")
            form = {
                "username": self.userName,
                "password": self.password,
                "login_submit": "登录/Login"
            }
            r = self.http_post("https://oauth.shu.edu.cn/login", data=form)
            if "认证失败" in r.text:
                raise PasswordError
            if "连续出错次数太多" in r.text:
                raise TryTooManyError("登录失败次数太多")
            if not r.url.startswith("http://www.elearning.shu.edu.cn/sso/logind"):
                raise LoginFailedError(2, f"unexpected url(2): {r.url}")
        else:
            error = f"login failed. unexpected url(1): {r.url}"
            self._logger.critical(error)
            raise LoginFailedError(1, error)

        # step 3
        # r.url start with http://www.elearning.shu.edu.cn/sso/logind
        html = lxml.etree.HTML(r.text)
        form = html.xpath("//form[@id='userLogin']")[0]
        inputs = form.xpath("input[@type='hidden']")
        request_url = form.attrib["action"]
        data = dict()
        for i in inputs:
            name = i.attrib["name"]
            value = i.attrib["value"]
            data[name] = value
            if name == "fid":
                fid = value
        r = self.http_post(request_url, data=data)

        if r.url != "http://www.elearning.shu.edu.cn/portal":
            raise LoginFailedError(3, f"unexpected url(3): {r.url}")

        # step 4
        params = {"fid": fid}
        self.http_get(
            "http://www.elearning.shu.edu.cn/setcookie.jsp", params=params)

    @cache(86400)
    def get_term_id_list(self, disable_cache=False) -> List[Tuple[int, str]]:
        """获取学期id
        @return [(20193, "2019-2020学年春季学期"), (20192, "2019-2020学年秋季学期"), ...]
        """
        # step 1 获取请求url
        r = self.http_get("http://i.mooc.elearning.shu.edu.cn/space/index.shtml",
                          referer="http://www.elearning.shu.edu.cn/portal")
        url = extract_string(
            r.text, "http://www.elearning.shu.edu.cn/courselist/study?s=")
        self._logger.info(f"get_term_id_list request url: {url}")
        # step 2
        result = list()
        r = self.http_get(url)
        html = lxml.etree.HTML(r.text)
        term_list_li = html.xpath(
            "//ul[@class='zse_ul']/li[@class='zse_li']/a")
        for x in term_list_li:
            year = x.xpath("@data_year")[0]
            term = x.xpath("@data_term")[0]
            comment = x.text.strip()
            try:
                term_id = int(year + term)
            except ValueError as e:
                self._logger.error(f"term_id转换错误：{e}, 略过：{comment}")
                term_id = -2
            result.append((term_id, comment))
        result.sort(key=lambda x: x[0], reverse=True)
        self._logger.info(f"term_id: {result}")
        return result

    @cache(86400)
    def get_course_list(self, term_id: int = -1, disable_cache=False) -> List[CourseInfo]:
        """获取课程列表
        @params term_id 学期ID，-1表示当前学期, 0表示所有课程。20193表示2019-2020春季学期。

        @return [CourseInfo(pageUrl='', courseName='', teacherName='', courseSeq=''), ...]
        """
        # step 1 获取请求url
        r = self.http_get("http://i.mooc.elearning.shu.edu.cn/space/index.shtml",
                          referer="http://www.elearning.shu.edu.cn/portal")
        url = extract_string(
            r.text, "http://www.elearning.shu.edu.cn/courselist/study?s=")
        self._logger.info(f"get_course_list request url: {url}")

        # step 2
        term_id_list = self.get_term_id_list()
        request_data = {
            "year": "0",
            "term": "0",
            "showContent": "000"
        }
        if term_id == -1:
            term_id = term_id_list[0][0]
        if term_id // 10000 == 2:
            request_data["year"] = str(term_id // 10)
            request_data["term"] = str(term_id % 10)
        elif term_id != 0:
            raise ValueError(f"invalid term_id: {term_id}")
        self._logger.debug(f"get_course_list term_id: {term_id}")

        r = self.http_get(url, params=request_data)
        html = lxml.etree.HTML(r.text)
        courses = html.xpath("//li[contains(@class, 'zmy_item')]")
        course_list = list()
        for c in courses:
            course_list.append(CourseInfo(
                pageUrl=c.xpath("a/@href")[0],
                courseName=c.xpath(
                    "dl/dt[@name='courseNameHtml']")[0].text.strip(),
                teacherName=c.xpath(
                    "dl/dd[@name='userNameHtml']")[0].text.strip(),
                courseSeq=c.xpath("dl/dt/span/text()")[0].strip()[1:-1]
            ))
        return course_list

    @cache(600)
    def get_work_list(self, page_url, disable_cache=False) -> List[WorkInfo]:
        """获取作业列表
        """
        result = list()
        r = self.http_get(page_url)
        # step 1 获取url
        request_path = extract_string(r.text, "/work/getAllWork?")
        request_url = "http://mooc1.elearning.shu.edu.cn" + request_path
        self._logger.info(f"get_work_list request_url: {request_url}")

        query_data = get_params_from_url(request_url)
        class_id = query_data["classId"]
        course_id = query_data["courseId"]
        cpi = query_data["cpi"]

        # step 2
        r = self.http_get(request_url)
        # 获取参数 enc
        # r.text 有如下一段，从里面提取参数 enc.
        # 注意，这个 enc 和 request_url 里面的 enc 并不一致。
        """
        url = "/work/doHomeWorkNew?courseId=" + courseId + "&classId=" + classId + "&workId=" + workRelationId + "&workAnswerId="
                + workRelationAnswerId + "&isdisplaytable=2&mooc=1&enc=f7b9e17b6c978b006dea24fcc54cbbe7&workSystem=0&cpi=64590381&standardEnc=";
            } else if (redit == 1) {
                url = "/work/doHomeWorkNew?courseId=" + courseId + "&classId=" + classId + "&workId=" + workRelationId + "&workAnswerId=" 
                    + workRelationAnswerId + "&reEdit=1&isdisplaytable=2&mooc=1&enc=f7b9e17b6c978b006dea24fcc54cbbe7&workSystem=0&cpi=64590381&standardEnc=";
            }
        """
        enc = None
        try:
            temp = r.text.index("/work/doHomeWorkNew")
            substr = r.text[temp:temp + 500]
            enc_list = re.findall("&enc=(.*?)&", substr)
            if enc_list:
                enc = enc_list[0]
        except ValueError as e:
            self._logger.debug(f"获取 enc 失败：{e}")
        # 获取 enc 完成

        html = lxml.etree.HTML(r.text)
        works = html.xpath("//div[@class='ulDiv']/ul/li")
        self._logger.info(f"get_work_list len(works) = {len(works)}")
        for x in works:
            work_name = x.xpath("div[@class='titTxt']/p/a/@title")[0]
            # 处理时间
            # t[0] - startTime, t[1] - endTime
            t = x.xpath("div[@class='titTxt']/span[@class='pt5']/text()")
            # 去除空格
            t = [i.strip() for i in t]
            time_format = r"%Y-%m-%d %H:%M"
            start_time = datetime.strptime(t[0], time_format) if t[0] else None
            end_tim = datetime.strptime(t[1], time_format) if t[1] else None
            # 作业状态
            work_status = x.xpath(
                "div[@class='titTxt']/span/strong")[0].text.strip()

            work_action_button = x.xpath(".//span[contains(text(), '做作业')]/..")
            work_relation_id = None
            work_relation_answer_id = None
            work_re_edit = None
            if work_action_button:
                work_action_button = work_action_button[0]
                work_relation_id = work_action_button.attrib.get("data")
                work_relation_answer_id = work_action_button.attrib.get("data")
                work_re_edit = work_action_button.attrib.get("data3")

            result.append(WorkInfo(
                workName=work_name,
                startTime=start_time,
                endTime=end_tim,
                workStatus=work_status,
                courseId=course_id,
                classId=class_id,
                workRelationId=work_relation_id,
                workRelationAnswerId=work_relation_answer_id,
                workReEdit=work_re_edit,
                enc=enc,
                cpi=cpi
            ))
        return result

    @cache(600)
    def get_unfinish_work_list(self, term_id=-1, disable_cache=False):
        """获取未完成作业。即状态为：待做
        @return [(CourseInfo, [WorkInfo, ...]), ...]
        """
        course_list = self.get_course_list(
            term_id=term_id, disable_cache=disable_cache)
        result = list()
        for course in course_list:
            work_list = self.get_work_list(
                course.pageUrl, disable_cache=disable_cache)
            unfinished_works = [x for x in work_list if x.workStatus == "待做"]
            if unfinished_works:
                result.append((course, unfinished_works))
        return result

    def dump_to(self, file_path=None):
        if file_path is None:
            file_path = self.load_file
        if file_path is None:
            raise ValueError("need param file_path")
        self._logger.debug(f"dump object to {file_path}")
        with open(file_path, "wb") as f:
            # 避开 python3.6 的一个 bug, 参考：https://bugs.python.org/issue30520
            del self._logger
            pickle.dump(self, f)

    @staticmethod
    def load_from(file_path):
        with open(file_path, "rb") as f:
            obj = pickle.load(f)
            obj.load_file = file_path
            if not hasattr(obj, "_logger"):
                obj._logger = logging.getLogger(__name__)
            return obj
