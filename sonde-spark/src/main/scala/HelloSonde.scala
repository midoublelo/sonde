package com.milloevers.sonde

import org.apache.spark.sql.SparkSession

/** Minimal test: confirms sbt, Scala 2.13, and Spark are all wired up
 * correctly before any real TfL/weather logic is written.
 *
 * Run with: sbt run
 * (or, once packaged: spark-submit --class com.milloevers.sonde.HelloSonde <jar>)
 */
object HelloSonde {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession
      .builder()
      .appName("sonde-spark-test")
      .master("local[*]")
      .getOrCreate()

    import spark.implicits._

    val stations = Seq(
      ("Oxford Circus", "Central", 2),
      ("King's Cross", "Northern", 0),
      ("Bank", "Central", 5)
    ).toDF("station", "line", "delay_minutes")

    println("=== Sonde Spark Test ===")
    stations.show()

    val avgDelay = stations.agg(org.apache.spark.sql.functions.avg("delay_minutes"))
    avgDelay.show()

    spark.stop()
  }
}