package com.milloevers.sonde

import com.milloevers.sonde.analysis.SeverityAnalysis
import com.milloevers.sonde.ingest.JsonlLoader
import com.milloevers.sonde.model.{TflLineStatus, WeatherReading}
import org.apache.spark.sql.{DataFrame, SparkSession}

/** Computes the severity analyses and writes them out as Parquet, for
 * Sonde's Streamlit dashboard to read (see src/analytics/spark_results.py
 * on the Python side).
 *
 * Run with: sbt run
 */
object WriteAnalysisOutputs {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession
      .builder()
      .appName("sonde-write-analysis-outputs")
      .master("local[*]")
      .getOrCreate()

    import spark.implicits._

    val tflPath = "../data/logs/tube_status.jsonl"
    val weatherPath = "../data/logs/weather.jsonl"
    val outputDir = "../data/spark_analysis"

    val tflStatuses = JsonlLoader.load[TflLineStatus](spark, tflPath)
    val weatherReadings = JsonlLoader.load[WeatherReading](spark, weatherPath)

    def writeSingleParquet(df: DataFrame, name: String): Unit =
      df.coalesce(1).write.mode("overwrite").parquet(s"$outputDir/$name")

    writeSingleParquet(SeverityAnalysis.avgSeverityByLine(tflStatuses), "avg_severity_by_line")
    writeSingleParquet(
      SeverityAnalysis.avgSeverityByWeather(tflStatuses, weatherReadings),
      "avg_severity_by_weather"
    )
    writeSingleParquet(
      SeverityAnalysis.weatherCorrelations(tflStatuses, weatherReadings),
      "weather_correlations"
    )

    println(s"Wrote Spark analysis outputs to $outputDir")

    spark.stop()
  }
}