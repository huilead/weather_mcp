from pydantic import BaseModel
from typing import List, Dict

class DayNightWeather(BaseModel):
    """日夜天气信息"""
    weather: str
    temperature: int
    wind_direction: str
    wind_power: str
    humidity: int

class WeatherInfo(BaseModel):
    """单日天气信息"""
    date: str
    week: str
    day: DayNightWeather
    night: DayNightWeather

class Forecast(BaseModel):
    """预报信息"""
    province: str
    city: str
    district: str
    adcode: int
    update_time: str
    infos: List[WeatherInfo]

class WeatherModel(BaseModel):
    """天气信息模型"""
    status: int
    result: Dict[str, List[Forecast]]