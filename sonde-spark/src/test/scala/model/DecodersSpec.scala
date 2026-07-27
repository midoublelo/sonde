package com.milloevers.sonde.model

import io.circe.parser.decode
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class DecodersSpec extends AnyFlatSpec with Matchers {

  "TflLineStatus decoder" should "decode a line with a delay reason" in {
    val json =
      """{"line_id": "northern", "line_name": "Northern", "status_severity": 6, "status_description": "Severe Delays", "reason": "Northern Line: Severe delays due to an earlier signal failure at Euston. Tickets being accepted on London Buses.  ", "polled_at": "2026-07-26T12:33:37.969704+00:00"}"""

    val result = decode[TflLineStatus](json)

    result.isRight shouldBe true
    val status = result.getOrElse(fail("decode failed"))
    status.lineId shouldBe "northern"
    status.lineName shouldBe "Northern"
    status.statusSeverity shouldBe 6
    status.statusDescription shouldBe "Severe Delays"
    status.reason shouldBe defined
  }

  it should "decode a line with a null reason as None" in {
    val json =
      """{"line_id": "piccadilly", "line_name": "Piccadilly", "status_severity": 10, "status_description": "Good Service", "reason": null, "polled_at": "2026-07-26T12:33:37.969704+00:00"}"""

    val result = decode[TflLineStatus](json)

    result.isRight shouldBe true
    result.getOrElse(fail("decode failed")).reason shouldBe None
  }

  "WeatherReading decoder" should "decode a reading with null rain and snow" in {
    val json =
      """{"temp_c": 18.16, "feels_like_c": 17.7, "humidity_pct": 64, "wind_speed_mps": 2.24, "weather_main": "Clouds", "weather_description": "few clouds", "rain_1h_mm": null, "snow_1h_mm": null, "polled_at": "2026-07-26T23:16:55.924296+00:00"}"""

    val result = decode[WeatherReading](json)

    result.isRight shouldBe true
    val reading = result.getOrElse(fail("decode failed"))
    reading.tempC shouldBe 18.16
    reading.weatherMain shouldBe "Clouds"
    reading.rain1hMm shouldBe None
    reading.snow1hMm shouldBe None
  }

  "TimeDecoders" should "decode timestamps with an explicit UTC offset" in {
    val json =
      """{"line_id": "victoria", "line_name": "Victoria", "status_severity": 9, "status_description": "Minor Delays", "reason": null, "polled_at": "2026-07-26T12:33:37.969704+00:00"}"""

    val result = decode[TflLineStatus](json)
    result.isRight shouldBe true
    result.getOrElse(fail("decode failed")).polledAt shouldBe java.time.Instant.parse("2026-07-26T12:33:37.969704Z")
  }

  it should "fall back to treating a naive (no-offset) timestamp as UTC" in {
    // Some older records were written without a timezone offset at all —
    // this is the case the fallback in TimeDecoders exists to handle.
    val json =
      """{"line_id": "victoria", "line_name": "Victoria", "status_severity": 9, "status_description": "Minor Delays", "reason": null, "polled_at": "2026-07-18T23:24:37.433243"}"""

    val result = decode[TflLineStatus](json)
    result.isRight shouldBe true
    result.getOrElse(fail("decode failed")).polledAt shouldBe java.time.Instant.parse("2026-07-18T23:24:37.433243Z")
  }
}