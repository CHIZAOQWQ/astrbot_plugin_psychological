#!/usr/bin/env python3
"""
API 测试脚本
用于测试心理委员插件中所有 API 的可用性
"""

import asyncio
import aiohttp
import json
from typing import Optional


# 返回 JSON 格式的 API（需要解析图片 URL）
JSON_API_LIST = [
    "https://v2.xxapi.cn/api/baisi",
    "https://v2.xxapi.cn/api/heisi",
]

# 直接返回图片的 API
IMAGE_API_LIST = []

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


async def test_json_api(api_url: str) -> tuple[bool, str, Optional[str]]:
    """
    测试返回 JSON 格式的 API
    
    Returns:
        (success, message, image_url)
    """
    try:
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, headers=HEADERS, allow_redirects=False) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                
                if "json" in content_type:
                    json_data = await response.json()
                    if isinstance(json_data, dict):
                        img_url = json_data.get("data")
                        if img_url and isinstance(img_url, str) and (img_url.startswith("http://") or img_url.startswith("https://")):
                            # 验证图片 URL 是否可访问
                            try:
                                async with session.get(img_url, headers=HEADERS) as img_response:
                                    img_response.raise_for_status()
                                    img_data = await img_response.read()
                                    if img_data and len(img_data) >= 100:
                                        return True, f"✓ 成功 - 图片 URL: {img_url[:80]}... (大小: {len(img_data)} bytes)", img_url
                                    else:
                                        return False, f"✗ 图片数据无效或太小 (大小: {len(img_data) if img_data else 0} bytes)", None
                            except Exception as e:
                                return False, f"✗ 图片 URL 无法访问: {str(e)}", img_url
                        else:
                            return False, f"✗ JSON 数据字段无效: {json_data}", None
                    else:
                        return False, f"✗ 返回的不是字典格式: {type(json_data)}", None
                else:
                    return False, f"✗ 内容类型不是 JSON: {content_type}", None
    except asyncio.TimeoutError:
        return False, "✗ 请求超时", None
    except aiohttp.ClientError as e:
        return False, f"✗ 网络错误: {str(e)}", None
    except Exception as e:
        return False, f"✗ 未知错误: {str(e)}", None


async def test_image_api(api_url: str) -> tuple[bool, str, Optional[bytes]]:
    """
    测试直接返回图片的 API
    
    Returns:
        (success, message, image_data)
    """
    try:
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, headers=HEADERS, allow_redirects=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                
                if "image" in content_type:
                    img_data = await response.read()
                    if img_data and len(img_data) >= 100:
                        return True, f"✓ 成功 - 图片大小: {len(img_data)} bytes, 类型: {content_type}", img_data
                    else:
                        return False, f"✗ 图片数据无效或太小 (大小: {len(img_data) if img_data else 0} bytes)", None
                elif "text" in content_type:
                    text_content = await response.text()
                    text_content = text_content.strip()
                    if text_content.startswith("http://") or text_content.startswith("https://"):
                        # 再次请求图片
                        try:
                            async with session.get(text_content, headers=HEADERS) as img_response:
                                img_response.raise_for_status()
                                img_data = await img_response.read()
                                if img_data and len(img_data) >= 100:
                                    return True, f"✓ 成功 - 返回 URL: {text_content[:80]}... (大小: {len(img_data)} bytes)", img_data
                                else:
                                    return False, f"✗ 图片数据无效或太小", None
                        except Exception as e:
                            return False, f"✗ 图片 URL 无法访问: {str(e)}", None
                    else:
                        return False, f"✗ 返回的文本不是 URL: {text_content[:100]}", None
                else:
                    return False, f"✗ 内容类型不是图片: {content_type}", None
    except asyncio.TimeoutError:
        return False, "✗ 请求超时", None
    except aiohttp.ClientError as e:
        return False, f"✗ 网络错误: {str(e)}", None
    except Exception as e:
        return False, f"✗ 未知错误: {str(e)}", None


async def run_tests():
    """运行所有 API 测试"""
    print("=" * 80)
    print("心理委员插件 API 测试")
    print("=" * 80)
    print()
    
    # 测试 JSON API
    print("【JSON API 测试】")
    print("-" * 80)
    json_results = []
    for api_url in JSON_API_LIST:
        print(f"测试: {api_url}")
        success, message, img_url = await test_json_api(api_url)
        json_results.append((api_url, success))
        print(f"  结果: {message}")
        if img_url:
            print(f"  图片 URL: {img_url}")
        print()
    
    # 测试图片 API
    print("【图片 API 测试】")
    print("-" * 80)
    image_results = []
    for api_url in IMAGE_API_LIST:
        print(f"测试: {api_url}")
        success, message, img_data = await test_image_api(api_url)
        image_results.append((api_url, success))
        print(f"  结果: {message}")
        print()
    
    # 汇总结果
    print("=" * 80)
    print("【测试汇总】")
    print("-" * 80)
    
    json_success = sum(1 for _, success in json_results if success)
    json_total = len(json_results)
    print(f"JSON API: {json_success}/{json_total} 成功")
    for api_url, success in json_results:
        status = "✓" if success else "✗"
        print(f"  {status} {api_url}")
    
    print()
    image_success = sum(1 for _, success in image_results if success)
    image_total = len(image_results)
    print(f"图片 API: {image_success}/{image_total} 成功")
    for api_url, success in image_results:
        status = "✓" if success else "✗"
        print(f"  {status} {api_url}")
    
    print()
    total_success = json_success + image_success
    total_apis = json_total + image_total
    print(f"总计: {total_success}/{total_apis} API 可用")
    
    if total_success == total_apis:
        print("\n🎉 所有 API 测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total_apis - total_success} 个 API 不可用")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_tests())
    exit(exit_code)
