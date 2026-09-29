from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger
from astrbot.api.all import Image
from astrbot.api.web import error_response, json_response, request
import aiohttp
import asyncio
import base64
import random
import time


PLUGIN_NAME = "astrbot_plugin_psychological_not_feeling_well"
PLUGIN_VERSION = "1.2.0"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


# 返回 JSON 格式的 API（需要解析图片 URL）
DEFAULT_JSON_API_LIST = [
    "https://v2.xxapi.cn/api/baisi",
    "https://v2.xxapi.cn/api/heisi",
    "https://v2.xxapi.cn/api/jk",
    "https://v2.xxapi.cn/api/yscos",
]

# 直接返回图片的 API
DEFAULT_IMAGE_API_LIST = []

# 随机提示语列表
WAITING_MESSAGES = [
    "稍等一下哦",
    "等我一下，马上就好~",
    "这样啊,给你看个好东西吧v(￣▽￣)v",
    "刚准备好，等等哦~",
    "巧了，我也不得劲",
    "希望这能让你心情好一点",
]


@register(
    PLUGIN_NAME,
    "是迟早a",
    "心理委员，我不得劲插件，输入 /心理委员 获取随机3次元美女图片",
    PLUGIN_VERSION,
)
class PsychologicalPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        context.register_web_api(
            f"/{PLUGIN_NAME}/api-test/list",
            self.api_test_list,
            ["GET"],
            "List configured APIs",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/api-test/run",
            self.api_test_run,
            ["POST"],
            "Test a configured API",
        )

    async def initialize(self):
        """插件初始化方法"""
        pass

    def _get_api_urls(self, config_key: str, default_urls: list[str]) -> list[str]:
        """读取并校验 WebUI 中配置的 API 地址列表。"""
        configured_urls = self.config.get(config_key, default_urls)
        if not isinstance(configured_urls, list):
            logger.warning(f"配置项 {config_key} 不是列表，将使用默认 API 列表")
            configured_urls = default_urls

        valid_urls = []
        for item in configured_urls:
            if not isinstance(item, str):
                logger.warning(f"忽略配置项 {config_key} 中的非字符串 API 地址: {item!r}")
                continue

            api_url = item.strip()
            if not api_url:
                continue
            if not api_url.startswith(("http://", "https://")):
                logger.warning(f"忽略配置项 {config_key} 中的无效 API 地址: {api_url}")
                continue
            if api_url not in valid_urls:
                valid_urls.append(api_url)

        return valid_urls

    async def api_test_list(self):
        """返回测试页面可选择的已配置 API。"""
        return json_response(
            {
                "json_api_list": self._get_api_urls(
                    "json_api_list", DEFAULT_JSON_API_LIST
                ),
                "image_api_list": self._get_api_urls(
                    "image_api_list", DEFAULT_IMAGE_API_LIST
                ),
            }
        )

    async def api_test_run(self):
        """请求指定 API，并返回可供测试页面预览的结果。"""
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("请求数据必须是 JSON 对象", status_code=400)

        api_type = payload.get("api_type")
        api_url = payload.get("api_url")
        if api_type not in ("json", "image"):
            return error_response("api_type 必须是 json 或 image", status_code=400)
        if not isinstance(api_url, str) or not api_url:
            return error_response("api_url 不能为空", status_code=400)

        config_key = "json_api_list" if api_type == "json" else "image_api_list"
        default_urls = (
            DEFAULT_JSON_API_LIST if api_type == "json" else DEFAULT_IMAGE_API_LIST
        )
        allowed_urls = self._get_api_urls(config_key, default_urls)
        if api_url not in allowed_urls:
            return error_response("该地址不在当前插件配置中", status_code=400)

        return json_response(await self._run_api_test(api_type, api_url))

    async def _run_api_test(self, api_type: str, api_url: str) -> dict:
        """执行单个 API 测试。"""
        started_at = time.perf_counter()
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        connector = aiohttp.TCPConnector(limit=2)

        async with aiohttp.ClientSession(
            timeout=timeout, connector=connector
        ) as session:
            if api_type == "json":
                api_result = await self._test_json_api(
                    session, api_url, REQUEST_HEADERS
                )
                if not api_result["success"]:
                    return self._test_result(
                        api_type, api_url, api_result, started_at
                    )
                image_url = api_result["image_url"]
            else:
                api_result = await self._test_image_api(
                    session, api_url, REQUEST_HEADERS
                )
                if not api_result["success"]:
                    return self._test_result(
                        api_type, api_url, api_result, started_at
                    )
                image_url = api_result["image_url"]

            image_result = await self._download_test_image(
                session, image_url, REQUEST_HEADERS
            )
            if not image_result["success"]:
                image_result["message"] = (
                    f"API 可用，但返回的图片无法访问: {image_result['message']}"
                )
                result = self._test_result(
                    api_type, api_url, image_result, started_at, image_url
                )
                result.update(
                    {
                        "api_status": api_result.get("status"),
                        "api_content_type": api_result.get("content_type"),
                    }
                )
                return result

            result = self._test_result(
                api_type, api_url, image_result, started_at, image_url
            )
            result.update(
                {
                    "api_status": api_result.get("status"),
                    "api_content_type": api_result.get("content_type"),
                    "image_status": image_result.get("status"),
                    "image_content_type": image_result.get("content_type"),
                    "size": len(image_result["image_data"]),
                    "image_data_url": self._to_data_url(
                        image_result["image_data"],
                        image_result["content_type"],
                    ),
                }
            )
            return result

    def _test_result(
        self,
        api_type: str,
        api_url: str,
        result: dict,
        started_at: float,
        image_url: str | None = None,
    ) -> dict:
        return {
            "success": bool(result.get("success")),
            "message": result.get("message", ""),
            "api_type": api_type,
            "api_url": api_url,
            "image_url": image_url or result.get("image_url"),
            "status": result.get("status"),
            "content_type": result.get("content_type"),
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        }

    async def _test_json_api(
        self,
        session: aiohttp.ClientSession,
        api_url: str,
        headers: dict,
    ) -> dict:
        """请求 JSON API，并提取图片 URL。"""
        status = None
        content_type = ""
        try:
            async with session.get(
                api_url, headers=headers, allow_redirects=False
            ) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "").lower()
                response.raise_for_status()
                if "json" not in content_type:
                    return {
                        "success": False,
                        "message": f"响应类型不是 JSON: {content_type or '未知'}",
                        "status": status,
                        "content_type": content_type,
                    }

                json_data = await response.json()
                if not isinstance(json_data, dict):
                    return {
                        "success": False,
                        "message": f"JSON 响应不是对象: {type(json_data)}",
                        "status": status,
                        "content_type": content_type,
                    }

                image_url = json_data.get("data")
                if not self._is_http_url(image_url):
                    return {
                        "success": False,
                        "message": "JSON 的 data 字段不是有效图片 URL",
                        "status": status,
                        "content_type": content_type,
                    }

                return {
                    "success": True,
                    "message": "JSON 接口请求成功",
                    "status": status,
                    "content_type": content_type,
                    "image_url": image_url,
                }
        except Exception as exc:
            return {
                "success": False,
                "message": f"请求失败: {str(exc) or type(exc).__name__}",
                "status": status,
                "content_type": content_type,
            }

    async def _test_image_api(
        self,
        session: aiohttp.ClientSession,
        api_url: str,
        headers: dict,
    ) -> dict:
        """请求直接返回图片或纯文本 URL 的 API。"""
        status = None
        content_type = ""
        try:
            async with session.get(
                api_url, headers=headers, allow_redirects=True
            ) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "").lower()
                response.raise_for_status()

                if "image" in content_type:
                    image_data = await response.read()
                    if len(image_data) < 100:
                        return {
                            "success": False,
                            "message": "图片数据过小",
                            "status": status,
                            "content_type": content_type,
                        }
                    return {
                        "success": True,
                        "message": "图片接口请求成功",
                        "status": status,
                        "content_type": content_type,
                        "image_url": api_url,
                        "image_data": image_data,
                    }

                if "text" in content_type:
                    image_url = (await response.text()).strip()
                    if not self._is_http_url(image_url):
                        return {
                            "success": False,
                            "message": "文本响应不是有效的图片 URL",
                            "status": status,
                            "content_type": content_type,
                        }
                    return {
                        "success": True,
                        "message": "图片接口返回了图片 URL",
                        "status": status,
                        "content_type": content_type,
                        "image_url": image_url,
                    }

                return {
                    "success": False,
                    "message": f"响应类型不是图片: {content_type or '未知'}",
                    "status": status,
                    "content_type": content_type,
                }
        except Exception as exc:
            return {
                "success": False,
                "message": f"请求失败: {str(exc) or type(exc).__name__}",
                "status": status,
                "content_type": content_type,
            }

    async def _download_test_image(
        self,
        session: aiohttp.ClientSession,
        image_url: str,
        headers: dict,
    ) -> dict:
        """下载图片 URL，供测试页面预览。"""
        status = None
        content_type = ""
        try:
            async with session.get(
                image_url, headers=headers, allow_redirects=True
            ) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "").lower()
                response.raise_for_status()
                if "image" not in content_type:
                    return {
                        "success": False,
                        "message": f"图片 URL 响应类型不是图片: {content_type or '未知'}",
                        "status": status,
                        "content_type": content_type,
                    }

                image_data = await response.read()
                if len(image_data) < 100:
                    return {
                        "success": False,
                        "message": "图片数据过小",
                        "status": status,
                        "content_type": content_type,
                    }

                return {
                    "success": True,
                    "message": "图片下载成功",
                    "status": status,
                    "content_type": content_type,
                    "image_data": image_data,
                }
        except Exception as exc:
            return {
                "success": False,
                "message": f"请求失败: {str(exc) or type(exc).__name__}",
                "status": status,
                "content_type": content_type,
            }

    @staticmethod
    def _is_http_url(value) -> bool:
        return isinstance(value, str) and value.startswith(("http://", "https://"))

    @staticmethod
    def _to_data_url(image_data: bytes, content_type: str) -> str:
        media_type = content_type.split(";", 1)[0].strip() or "image/jpeg"
        encoded = base64.b64encode(image_data).decode("ascii")
        return f"data:{media_type};base64,{encoded}"

    async def _fetch_json_api(self, session: aiohttp.ClientSession, api_url: str, headers: dict) -> str | None:
        """处理返回 JSON 格式的 API，解析并返回图片 URL"""
        try:
            async with session.get(api_url, headers=headers, allow_redirects=False) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                
                # 检查是否为 JSON 响应
                if "json" in content_type:
                    json_data = await response.json()
                    # 根据 API 返回格式解析图片 URL
                    # 格式: {"code": 200, "msg": "...", "data": "图片URL", ...}
                    if isinstance(json_data, dict):
                        img_url = json_data.get("data")
                        if img_url and isinstance(img_url, str) and (img_url.startswith("http://") or img_url.startswith("https://")):
                            logger.info(f"从 JSON API 获取到图片 URL: {img_url}")
                            return img_url
                        else:
                            logger.warning(f"JSON API 返回的数据字段无效: {json_data}")
                            return None
                    else:
                        logger.warning(f"JSON API 返回的不是字典格式: {type(json_data)}")
                        return None
                else:
                    logger.warning(f"JSON API 返回的内容类型不是 JSON: {content_type}")
                    return None
        except Exception as e:
            logger.error(f"处理 JSON API 时发生错误: {str(e)}")
            return None

    async def _fetch_image_api(self, session: aiohttp.ClientSession, api_url: str, headers: dict) -> bytes | None:
        """处理直接返回图片的 API，返回图片数据"""
        try:
            async with session.get(api_url, headers=headers, allow_redirects=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                
                # 检查是否为图片响应
                if "image" in content_type:
                    img_data = await response.read()
                    if img_data and len(img_data) >= 100:
                        logger.info(f"从图片 API 获取到图片数据，大小: {len(img_data)} bytes")
                        return img_data
                    else:
                        logger.warning("获取的图片数据无效或太小")
                        return None
                # 某些 API 可能返回纯文本 URL
                elif "text" in content_type:
                    text_content = await response.text()
                    text_content = text_content.strip()
                    if text_content.startswith("http://") or text_content.startswith("https://"):
                        logger.info(f"图片 API 返回了 URL，再次请求: {text_content}")
                        # 再次请求图片
                        async with session.get(text_content, headers=headers) as img_response:
                            img_response.raise_for_status()
                            img_data = await img_response.read()
                            if img_data and len(img_data) >= 100:
                                return img_data
                else:
                    logger.warning(f"图片 API 返回的内容类型不是图片: {content_type}")
                    return None
        except Exception as e:
            logger.error(f"处理图片 API 时发生错误: {str(e)}")
            return None

    @filter.command("心理委员")
    async def psychological(self, event: AstrMessageEvent):
        """心理委员指令，随机返回一张图片"""
        # 随机选择一条提示语
        waiting_msg = random.choice(WAITING_MESSAGES)
        yield event.plain_result(waiting_msg)

        # 合并所有 API 列表并打乱，增加随机性
        all_apis = []
        json_api_urls = self._get_api_urls("json_api_list", DEFAULT_JSON_API_LIST)
        image_api_urls = self._get_api_urls("image_api_list", DEFAULT_IMAGE_API_LIST)
        for api_url in json_api_urls:
            all_apis.append(("json", api_url))
        for api_url in image_api_urls:
            all_apis.append(("image", api_url))
        random.shuffle(all_apis)

        # 创建会话
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        connector = aiohttp.TCPConnector(limit=10)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # 尝试每个API，直到成功
        last_error = None
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            for api_type, api_url in all_apis:
                try:
                    logger.info(f"尝试使用 {api_type.upper()} API: {api_url}")

                    if api_type == "json":
                        # 处理返回 JSON 的 API
                        img_url = await self._fetch_json_api(session, api_url, headers)
                        if img_url:
                            # 使用 Image.fromURL 发送图片
                            yield event.chain_result([Image.fromURL(img_url)])
                            logger.info("图片发送成功（通过 URL）")
                            return
                    else:
                        # 处理直接返回图片的 API
                        img_data = await self._fetch_image_api(session, api_url, headers)
                        if img_data:
                            # 使用 Image.fromBytes 发送图片
                            yield event.chain_result([Image.fromBytes(img_data)])
                            logger.info("图片发送成功（通过字节数据）")
                            return

                except (asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
                    last_error = f"请求超时: {api_url}"
                    logger.warning(f"API请求超时: {api_url}")
                    continue
                except aiohttp.ClientError as e:
                    last_error = f"网络错误: {str(e) or type(e).__name__}"
                    logger.warning(f"API请求错误 ({api_url}): {str(e) or type(e).__name__}")
                    continue
                except Exception as e:
                    last_error = f"未知错误: {str(e) or type(e).__name__}"
                    logger.error(f"处理API时发生错误 ({api_url}): {str(e) or type(e).__name__}", exc_info=True)
                    continue

        # 所有API都失败了
        error_msg = last_error or "所有API都无法访问"
        logger.error(f"所有API都失败，最后错误: {error_msg}")
        yield event.plain_result(f"获取图片失败，请稍后再试")

    async def terminate(self):
        """插件销毁方法"""
        pass
