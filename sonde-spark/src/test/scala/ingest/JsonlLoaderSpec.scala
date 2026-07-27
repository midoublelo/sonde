package com.milloevers.sonde.ingest

import com.milloevers.sonde.model.TflLineStatus
import org.apache.spark.sql.SparkSession
import org.scalatest.BeforeAndAfterAll
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

import java.nio.file.{Files, Path}
import scala.jdk.CollectionConverters._

class JsonlLoaderSpec extends AnyFlatSpec with Matchers with BeforeAndAfterAll {

  private var spark: SparkSession = _
  private var tempFile: Path = _

  override def beforeAll(): Unit = {
    spark = SparkSession
      .builder()
      .appName("jsonl-loader-tests")
      .master("local[2]")
      .getOrCreate()

    val validLine1 =
      """{"line_id": "victoria", "line_name": "Victoria", "status_severity": 9, "status_description": "Minor Delays", "reason": "Victoria Line: Minor delays.", "polled_at": "2026-07-26T12:33:37.969704+00:00"}"""
    val validLine2 =
      """{"line_id": "piccadilly", "line_name": "Piccadilly", "status_severity": 10, "status_description": "Good Service", "reason": null, "polled_at": "2026-07-26T12:33:37.969704+00:00"}"""
    val malformedLine = """{"line_id": "broken", this is not valid json"""

    tempFile = Files.createTempFile("jsonl-loader-test", ".jsonl")
    Files.write(tempFile, List(validLine1, malformedLine, validLine2).asJava)
  }

  override def afterAll(): Unit = {
    if (spark != null) spark.stop()
    if (tempFile != null) Files.deleteIfExists(tempFile)
  }

  "JsonlLoader" should "load valid lines and skip malformed ones without failing" in {
    val sparkSession = spark
    import sparkSession.implicits._

    val result = JsonlLoader.load[TflLineStatus](spark, tempFile.toString)

    result.count() shouldBe 2

    val lineIds = result.collect().map(_.lineId).toSet
    lineIds shouldBe Set("victoria", "piccadilly")
  }
}