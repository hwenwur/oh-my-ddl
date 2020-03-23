import requests
import logging
import lxml.etree
from collections import namedtuple
import pickle
from datetime import datetime
import time
from typing import List, Dict, Tuple
from .utils import extract_string


WorkInfo = namedtuple("WorkInfo", ["workName", "startTime", "endTime", "workStatus"])
CourseInfo = namedtuple("CourseInfo", ["pageUrl", "courseName", "teacherName", "courseSeq"])


class ChaoxingUser:
    HTTP_HEADERS = {
        # dummy user-agent
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13) AppleWebKit/603.1.13 (KHTML, like Gecko) Version/10.1 Safari/603.1.13',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7"
    }
    CACHE_EXPIRE_TIME = 600

    def __init__(self, userName, password):
        self.userName = userName
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(self.HTTP_HEADERS)
        self._logger = logging.getLogger(__name__)
        self._cache_table : Dict[str, Tuple[List, float]]= dict()

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
                    auto_retry -= 1
                    self._logger.error(f"自动重试: {auto_retry}")
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
        elif "beforLogin" in r.text:
            return False
        else:
            self._logger.error(f"无法判断登录状态。status_code:{r.status_code},text:\n{r.text}")
            raise RuntimeError("无法判断登录状态")

    def login(self):
        # step 1
        r = self.http_get("http://shu.fysso.chaoxing.com/sso/shu", referer="http://www.elearning.shu.edu.cn/portal")
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
            assert r.url.startswith("http://www.elearning.shu.edu.cn/sso/logind"), f"unexpected url(2): {r.url}"
        else:
            error = f"login failed. unexpected url(1): {r.url}"
            self._logger.critical(error)
            raise RuntimeError(error)

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
        assert r.url == "http://www.elearning.shu.edu.cn/portal", f"unexpected url(3): {r.url}"

        # step 4
        params = {"fid": fid}
        self.http_get("http://www.elearning.shu.edu.cn/setcookie.jsp", params=params)

    def get_course_list(self, useCache=True) -> List[CourseInfo]:
        """获取课程列表
        @return [CourseInfo(pageUrl='', courseName='', teacherName='', courseSeq=''), ...]
        """
        if useCache:
            cache = self._read_cache("course_list")
            if cache is not None:
                self._logger.info("get_course_list use cache value.")
                return cache
        # step 1 获取请求url
        r = self.http_get("http://i.mooc.elearning.shu.edu.cn/space/index.shtml", referer="http://www.elearning.shu.edu.cn/portal")
        url = extract_string(r.text, "http://www.elearning.shu.edu.cn/courselist/study?s=")
        self._logger.info(f"get_course_list request url: {url}")

        # step 2
        r = self.http_get(url)
        html = lxml.etree.HTML(r.text)
        courses = html.xpath("//li[contains(@class, 'zmy_item')]")
        course_list = list()
        for c in courses:
            course_list.append(CourseInfo(
                pageUrl=c.xpath("a/@href")[0],
                courseName=c.xpath("dl/dt[@name='courseNameHtml']")[0].text.strip(),
                teacherName=c.xpath("dl/dd[@name='userNameHtml']")[0].text.strip(),
                courseSeq=c.xpath("dl/dt/span/text()")[0].strip()[1:-1]
            ))
        self._write_cache("course_list", course_list)
        return course_list

    def get_work_list(self, page_url, useCache=True) -> List[WorkInfo]:
        """获取作业列表
        """
        if useCache:
            cache = self._read_cache("work_list_" + page_url)
            if cache is not None:
                self._logger.info("get_work_list use cache value")
                return cache
        result = list()
        r = self.http_get(page_url)
        # step 1 获取url
        request_path = extract_string(r.text, "/work/getAllWork?")
        request_url = "http://mooc1.elearning.shu.edu.cn" + request_path
        self._logger.info(f"get_work_list request_url: {request_url}")
        # step 2
        r = self.http_get(request_url)
        html = lxml.etree.HTML(r.text)
        works = html.xpath("//div[@class='ulDiv']/ul/li")
        self._logger.info(f"get_work_list len(works) = {len(works)}")
        for x in works:
            workName = x.xpath("div[@class='titTxt']/p/a/@title")[0]
            t = x.xpath("div[@class='titTxt']/span[@class='pt5']/text()")
            t = [i.strip() for i in t]
            time_format = r"%Y-%m-%d %H:%M"
            startTime = datetime.strptime(t[0], time_format) if t[0] else None
            endTime = datetime.strptime(t[1], time_format) if t[1] else None
            workStatus = x.xpath("div[@class='titTxt']/span/strong")[0].text.strip()
            result.append(WorkInfo(
                workName=workName,
                startTime=startTime,
                endTime=endTime,
                workStatus=workStatus
            ))
        self._write_cache("work_list_" + page_url, result)
        return result

    def dump_to(self, file_path):
        self._logger.debug(f"dump object to {file_path}")
        with open(file_path, "wb") as f:
            pickle.dump(self, f)
    
    @staticmethod
    def load_from(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
