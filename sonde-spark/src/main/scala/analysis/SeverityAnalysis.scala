package com.milloevers.sonde.analysis

import com.milloevers.sonde.model.{TflLineStatus, WeatherReading}
import org.apache.spark.sql.{DataFrame, Dataset}
import org.apache.spark.sql.functions._
import org.slf4j.LoggerFactory

object SeverityAnalysis {

  private val logger = LoggerFactory.getLogger(getClass)

  private val ServiceClosedCode = 20

  private def excludingServiceClosed(tfl: Dataset[TflLineStatus]): Dataset[TflLineStatus] =
    tfl.filter(col("statusSeverity") =!= ServiceClosedCode)

  def avgSeverityByLine(tfl: Dataset[TflLineStatus]): DataFrame =
    excludingServiceClosed(tfl)
      .groupBy("lineId")
      .agg(
        avg("statusSeverity").as("avgSeverity"),
        count("*").as("recordCount")
      )
      .orderBy(desc("avgSeverity"))

  def avgSeverityByWeather(
                            tfl: Dataset[TflLineStatus],
                            weather: Dataset[WeatherReading]
                          ): DataFrame = {
    val tflBucketed = excludingServiceClosed(tfl)
      .withColumn("hourBucket", date_trunc("HOUR", col("polledAt")))
    val weatherBucketed = weather.withColumn("hourBucket", date_trunc("HOUR", col("polledAt")))

    tflBucketed
      .join(weatherBucketed, "hourBucket")
      .groupBy("weatherMain")
      .agg(
        avg("statusSeverity").as("avgSeverity"),
        count("*").as("recordCount")
      )
      .orderBy(desc("avgSeverity"))
  }

  def distinctSeverityCodes(tfl: Dataset[TflLineStatus]): DataFrame =
    tfl
      .select("statusSeverity", "statusDescription")
      .distinct()
      .orderBy("statusSeverity")

  def weatherCorrelations(
                           tfl: Dataset[TflLineStatus],
                           weather: Dataset[WeatherReading]
                         ): DataFrame = {
    val spark = tfl.sparkSession
    import spark.implicits._

    val tflHourly = excludingServiceClosed(tfl)
      .withColumn("hourBucket", date_trunc("HOUR", col("polledAt")))
      .groupBy("hourBucket")
      .agg(avg("statusSeverity").as("avgSeverity"))

    val weatherHourly = weather
      .na.fill(0.0, Seq("rain1hMm", "snow1hMm"))
      .withColumn("hourBucket", date_trunc("HOUR", col("polledAt")))
      .groupBy("hourBucket")
      .agg(
        avg("tempC").as("avgTempC"),
        avg("feelsLikeC").as("avgFeelsLikeC"),
        avg("humidityPct").as("avgHumidityPct"),
        avg("windSpeedMps").as("avgWindSpeedMps"),
        avg("rain1hMm").as("avgRain1hMm"),
        avg("snow1hMm").as("avgSnow1hMm")
      )

    val joined = tflHourly.join(weatherHourly, "hourBucket").cache()

    if (joined.isEmpty) {
      logger.warn("No overlapping hours between TfL and weather data — returning empty correlation table")
      return Seq.empty[(String, Double)].toDF("weatherVariable", "pearsonCorrelation")
    }

    val weatherColumns =
      Seq("avgTempC", "avgFeelsLikeC", "avgHumidityPct", "avgWindSpeedMps", "avgRain1hMm", "avgSnow1hMm")

    val severityHasVariance = joined.select(stddev_pop(col("avgSeverity"))).as[Double].head() > 0.0

    val correlations =
      if (!severityHasVariance) {
        logger.warn("avgSeverity has zero variance across hours in this data — skipping all correlations")
        Seq.empty[(String, Double)]
      } else {
        weatherColumns.flatMap { column =>
          val hasVariance = joined.select(stddev_pop(col(column))).as[Double].head() > 0.0
          if (hasVariance) {
            Some(column -> joined.stat.corr("avgSeverity", column))
          } else {
            logger.warn(s"Skipping correlation for '$column': zero variance in this data")
            None
          }
        }
      }

    correlations
      .toDF("weatherVariable", "pearsonCorrelation")
      .orderBy(abs($"pearsonCorrelation").desc)
  }
}