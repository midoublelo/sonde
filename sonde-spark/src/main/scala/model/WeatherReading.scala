package com.milloevers.sonde.model

import io.circe.Decoder
import com.milloevers.sonde.model.TimeDecoders._

import java.time.Instant

final case class WeatherReading(
    tempC: Double,
    feelsLikeC: Double,
    humidityPct: Int,
    windSpeedMps: Double,
    weatherMain: String,
    weatherDescription: String,
    rain1hMm: Option[Double],
    snow1hMm: Option[Double],
    polledAt: Instant
)

object WeatherReading {

  implicit val decoder: Decoder[WeatherReading] = Decoder.forProduct9(
    "temp_c",
    "feels_like_c",
    "humidity_pct",
    "wind_speed_mps",
    "weather_main",
    "weather_description",
    "rain_1h_mm",
    "snow_1h_mm",
    "polled_at"
  )(WeatherReading.apply)
}