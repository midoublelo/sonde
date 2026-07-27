package com.milloevers.sonde

import org.apache.spark.sql.SparkSession
import org.scalatest.BeforeAndAfterAll
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class HelloSondeSpec extends AnyFlatSpec with Matchers with BeforeAndAfterAll {

  private var spark: SparkSession = _

  override def beforeAll(): Unit = {
    spark = SparkSession
      .builder()
      .appName("sonde-spark-tests")
      .master("local[2]")
      .getOrCreate()
  }

  override def afterAll(): Unit = {
    if (spark != null) spark.stop()
  }

  "A simple DataFrame" should "count rows correctly" in {
    val sparkSession = spark
    import sparkSession.implicits._
    val df = Seq(("a", 1), ("b", 2), ("c", 3)).toDF("id", "value")
    df.count() shouldBe 3
  }

  it should "compute an average correctly" in {
    val sparkSession = spark
    import sparkSession.implicits._
    val df = Seq(1, 2, 3, 4).toDF("value")
    val avg = df.agg(org.apache.spark.sql.functions.avg("value")).first().getDouble(0)
    avg shouldBe 2.5
  }
}