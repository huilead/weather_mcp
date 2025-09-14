from fastmcp import FastMCP
from dotenv import load_dotenv
import os
import httpx

from weather_model import WeatherModel, Forecast, WeatherInfo, DayNightWeather

load_dotenv()

server = FastMCP("weather_mcp")

api_type = os.getenv("API_TYPE")
api_key = os.getenv("API_KEY")


if not api_key:
    raise ValueError("环境变量api_key未设置, 请检查 .env文件")

if not api_type:
    raise ValueError("环境变量api_type未设置, 请检查 .env文件")

async def _make_api_request(url: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectTimeout as e:
        raise Exception(f"连接错误: 无法连接到服务器 - {e}")
    except httpx.TimeoutException as e:
        raise Exception(f"请求超时: 请稍后重试 - {e}")
    except httpx.NetworkError as e:
        raise Exception(f"网络错误: 底层网络问题 - {e}")
    except httpx.HTTPStatusError as e:
        raise Exception(f"返回错误: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        raise Exception(f"其它错误：{e}")

async def _get_adcode_by_name(api_type: str, location_name: str) -> str:
    """根据地区名称获取地区编码"""
    if api_type == "tencent":
        url_adcode = f"https://apis.map.qq.com/ws/district/v1/search"
        params_adcode = {
            "key": api_key,
            "keyword": location_name
        }
        response = await _make_api_request(url_adcode, params_adcode)
        
        # 安全提取腾讯地图地区编码
        result = response.get("result", [])
        if not result or not isinstance(result, list) or len(result) == 0:
            raise Exception(f"请输出正确的城市名称或区县名称")
        
        first_result = result[0]
        if not isinstance(first_result, list) or len(first_result) == 0:
            raise Exception(f"请输出正确的城市名称或区县名称")
            
        weather_adcode = first_result[0].get("id", "")
        if not weather_adcode:
            raise Exception(f"请输出正确的城市名称或区县名称")
        
        return weather_adcode

    elif api_type == "amap":
        url_adcode = f"https://restapi.amap.com/v3/config/district"
        params_adcode = {
            "key": api_key,
            "keywords": location_name,
            "subdistrict": 0
        }
        response = await _make_api_request(url_adcode, params_adcode)
        
        # 安全提取高德地图地区编码
        districts = response.get("districts", [])
        if not districts or not isinstance(districts, list) or len(districts) == 0:
            raise Exception(f"请输出正确的城市名称或区县名称")
        
        weather_adcode = districts[0].get("adcode", "")
        if not weather_adcode:
            raise Exception(f"请输出正确的城市名称或区县名称")
        
        return weather_adcode


# async def get_weather(self, adcode: str) -> WeatherModel:
@server.tool()
async def get_weather(adcode: str) -> WeatherModel:
    """ 获取天气信息

    Args:
        adcode (str): 地区编码 或 地区名称

    Returns:
        WeatherModel: 天气信息
    """
    if not adcode.isdigit():
        weather_adcode = await _get_adcode_by_name(api_type, adcode)
    elif len(adcode) != 6:
        raise ValueError("请输入正确的地区编码")
    else:
        weather_adcode = str(adcode)


    if api_type == "tencent":        
        base_url = f"https://apis.map.qq.com/ws/weather/v1/"
        params = {
            "key": api_key,
            "adcode": weather_adcode,
            "type": "future",
            "get_md": 0
        }

    elif api_type == "amap":
        base_url = f"https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            "key": api_key,
            "city": weather_adcode,
            "extensions": "all"
        }
        
    response = await _make_api_request(base_url, params)    
    # 根据API类型处理返回数据并构建WeatherModel
    if api_type == "tencent":
        # 腾讯地图API返回格式处理
        weather_data = {
            "status": response.get("status", 0),
            "result": response.get("result", {})
        }
    elif api_type == "amap":
        # 高德地图API返回格式处理
        forecasts = response.get("forecasts", [])
        processed_forecasts = []
        
        for forecast_data in forecasts:
            # 解析天气信息列表
            weather_infos = []
            for info in forecast_data.get("casts", []):
                # 构建白天天气信息
                day_weather = DayNightWeather(
                    weather=info.get("dayweather", ""),
                    temperature=int(info.get("daytemp", 0)),
                    wind_direction=info.get("daywind", ""),
                    wind_power=info.get("daypower", ""),
                    humidity=int(info.get("dayhumidity", 0)) if info.get("dayhumidity") else 0
                )
                
                # 构建夜间天气信息
                night_weather = DayNightWeather(
                    weather=info.get("nightweather", ""),
                    temperature=int(info.get("nighttemp", 0)),
                    wind_direction=info.get("nightwind", ""),
                    wind_power=info.get("nightpower", ""),
                    humidity=int(info.get("nighthumidity", 0)) if info.get("nighthumidity") else 0
                )
                
                try:
                    week_num = int(info.get("week", 0))
                    week_name = ["未知", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][week_num]
                except (ValueError, IndexError):
                    week_name = "未知"

                # 构建单日天气信息
                weather_info = WeatherInfo(
                    date=info.get("date", ""),
                    # week=info.get("week", ""),
                    # 为了保证返回和腾讯地图的返回一致，这里将week设为中文星期
                    week=week_name,
                    day=day_weather,
                    night=night_weather
                )
                weather_infos.append(weather_info)
            
            # 构建预报信息
            forecast = Forecast(
                province=forecast_data.get("province", ""),
                city=forecast_data.get("city", ""),
                district=forecast_data.get("adcode", ""),
                adcode=int(forecast_data.get("adcode", 0)),
                update_time=forecast_data.get("reporttime", ""),
                infos=weather_infos
            )
            processed_forecasts.append(forecast)
        
        weather_data = {
            # "status": int(response.get("status", "0")),
            # 为了保证返回和腾讯地图的返回一致，这里将status设为0
            "status": 0,
            "result": {
                "forecast": processed_forecasts
            }
        }
    
    # 创建并返回WeatherModel实例
    return WeatherModel(**weather_data)

if __name__ == "__main__":
    server.run()


    # import asyncio    
    # # 脚本自测时使用，正式上线时删除或注释掉
    # async def main():
    #     await get_weather("杭州市")
    
    # asyncio.run(main())