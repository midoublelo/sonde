package com.milloevers.sonde

import com.milloevers.sonde.analysis.SeverityAnalysis
import com.milloevers.sonde.ingest.JsonlLoader
import com.milloevers.sonde.model.{TflLineStatus, WeatherReading}
import org.apache.spark.sql.SparkSession

/** Loads TfL and weather JSONL from Sonde's data/ folder and prints basic
  * counts, as a test for the ingest pipeline.
  *
  * Run with: sbt run
  */
object IngestDemo {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession
      .builder()
      .appName("sonde-ingest-demo")
      .master("local[*]")
      .getOrCreate()

    import spark.implicits._

    // sonde-spark/ sits alongside data/ in the repo, so "../data" is the
    // relative path from sonde-spark's working directory. Adjust the glob
    // to match your real filenames.
    val tflPath = "../data/logs/tube_status.jsonl"
    val weatherPath = "../data/logs/weather.jsonl"

    val tflStatuses = JsonlLoader.load[TflLineStatus](spark, tflPath)
    println(s"Loaded ${tflStatuses.count()} TfL line status records")
    tflStatuses.show(5, truncate = false)

    val weatherReadings = JsonlLoader.load[WeatherReading](spark, weatherPath)
    println(s"Loaded ${weatherReadings.count()} weather readings")
    weatherReadings.show(5, truncate = false)

    println("=== Distinct (severity, description) pairs seen in the data ===")
    SeverityAnalysis.distinctSeverityCodes(tflStatuses).show(50, truncate = false)

    println("=== Average severity per line ===")
    SeverityAnalysis.avgSeverityByLine(tflStatuses).show(truncate = false)

    println("=== Average severity per weather condition (hour-bucketed join) ===")
    SeverityAnalysis.avgSeverityByWeather(tflStatuses, weatherReadings).show(truncate = false)

    println("=== Pearson correlation: avg severity vs continuous weather variables (per hour) ===")
    SeverityAnalysis.weatherCorrelations(tflStatuses, weatherReadings).show(truncate = false)

    spark.stop()
  }
}