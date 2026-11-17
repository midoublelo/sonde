package com.milloevers.sonde.analysis

import com.milloevers.sonde.model.{TflLineStatus, WeatherReading}
import org.apache.spark.sql.SparkSession
import org.scalatest.BeforeAndAfterAll
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

import java.time.Instant

class SeverityAnalysisSpec extends AnyFlatSpec with Matchers with BeforeAndAfterAll {

  private var spark: SparkSession = _

  override def beforeAll(): Unit = {
    spark = SparkSession
      .builder()
      .appName("severity-analysis-tests")
      .master("local[2]")
      .config("spark.sql.session.timeZone", "UTC")
      .getOrCreate()
  }

  override def afterAll(): Unit = {
    if (spark != null) spark.stop()
  }

  "avgSeverityByLine" should "average severity correctly per line" in {
    val sparkSession = spark
    import sparkSession.implicits._

    val data = Seq(
      TflLineStatus("northern", "Northern", 6, "Severe Delays", Some("signal failure"), Instant.parse("2026-07-26T12:00:00Z")),
      TflLineStatus("northern", "Northern", 8, "Minor Delays", Some("points failure"), Instant.parse("2026-07-26T13:00:00Z")),
      TflLineStatus("piccadilly", "Piccadilly", 10, "Good Service", None, Instant.parse("2026-07-26T12:00:00Z"))
    ).toDS()

    val result = SeverityAnalysis.avgSeverityByLine(data).collect()

    val northernRow = result.find(_.getAs[String]("lineId") == "northern").get
    northernRow.getAs[Double]("avgSeverity") shouldBe 7.0
    northernRow.getAs[Long]("recordCount") shouldBe 2L

    val piccadillyRow = result.find(_.getAs[String]("lineId") == "piccadilly").get
    piccadillyRow.getAs[Double]("avgSeverity") shouldBe 10.0
  }

  it should "exclude Service Closed (code 20) records entirely" in {
    val sparkSession = spark
    import sparkSession.implicits._

    val data = Seq(
      TflLineStatus("victoria", "Victoria", 10, "Good Service", None, Instant.parse("2026-07-26T12:00:00Z")),
      TflLineStatus("victoria", "Victoria", 20, "Service Closed", None, Instant.parse("2026-07-27T02:00:00Z"))
    ).toDS()

    val result = SeverityAnalysis.avgSeverityByLine(data).collect()

    val victoriaRow = result.find(_.getAs[String]("lineId") == "victoria").get
    victoriaRow.getAs[Double]("avgSeverity") shouldBe 10.0
    victoriaRow.getAs[Long]("recordCount") shouldBe 1L
  }

  "avgSeverityByWeather" should "join on hour bucket and average severity per weather condition" in {
    val sparkSession = spark
    import sparkSession.implicits._

    val tfl = Seq(
      TflLineStatus("northern", "Northern", 6, "Severe Delays", Some("signal failure"), Instant.parse("2026-07-26T12:00:00Z")),
      TflLineStatus("victoria", "Victoria", 8, "Minor Delays", Some("points failure"), Instant.parse("2026-07-26T12:30:00Z")),
      TflLineStatus("piccadilly", "Piccadilly", 10, "Good Service", None, Instant.parse("2026-07-26T15:15:00Z"))
    ).toDS()

    val weather = Seq(
      WeatherReading(15.0, 14.0, 80, 3.0, "Rain", "light rain", Some(1.2), None, Instant.parse("2026-07-26T12:00:00Z")),
      WeatherReading(20.0, 19.5, 50, 1.0, "Clear", "clear sky", None, None, Instant.parse("2026-07-26T15:00:00Z"))
    ).toDS()

    val result = SeverityAnalysis.avgSeverityByWeather(tfl, weather).collect()

    val rainRow = result.find(_.getAs[String]("weatherMain") == "Rain").get
    rainRow.getAs[Double]("avgSeverity") shouldBe 7.0
    rainRow.getAs[Long]("recordCount") shouldBe 2L

    val clearRow = result.find(_.getAs[String]("weatherMain") == "Clear").get
    clearRow.getAs[Double]("avgSeverity") shouldBe 10.0
    clearRow.getAs[Long]("recordCount") shouldBe 1L
  }

  "disruptionRateByBucket" should "compute the unplanned-disruption rate per line/hour/daytype and exclude scheduled closures from the numerator" in {
    val sparkSession = spark
    import sparkSession.implicits._

    val data = Seq(
      TflLineStatus("central", "Central", 6, "Severe Delays", Some("signal failure"), Instant.parse("2026-07-27T12:00:00Z")),
      TflLineStatus("central", "Central", 8, "Minor Delays", None, Instant.parse("2026-07-27T12:15:00Z")),
      TflLineStatus("central", "Central", 4, "Planned Closure", None, Instant.parse("2026-07-27T12:30:00Z")),
      TflLineStatus("central", "Central", 10, "Good Service", None, Instant.parse("2026-07-27T12:45:00Z"))
    ).toDS()

    val result = SeverityAnalysis.disruptionRateByBucket(data).collect()

    result.length shouldBe 1
    val row = result.head
    row.getAs[String]("lineId") shouldBe "central"
    row.getAs[Int]("hour") shouldBe 13
    row.getAs[Boolean]("isWeekend") shouldBe false
    row.getAs[Double]("disruptionRate") shouldBe 0.5
    row.getAs[Long]("observations") shouldBe 4L
  }

  it should "treat Saturday as a weekend and separate it into its own bucket" in {
    val sparkSession = spark
    import sparkSession.implicits._

    val data = Seq(
      TflLineStatus("victoria", "Victoria", 6, "Severe Delays", None, Instant.parse("2026-07-25T10:00:00Z")),
      TflLineStatus("victoria", "Victoria", 10, "Good Service", None, Instant.parse("2026-07-27T10:00:00Z"))
    ).toDS()

    val result = SeverityAnalysis.disruptionRateByBucket(data).collect()

    val weekendRow = result.find(_.getAs[Boolean]("isWeekend")).get
    weekendRow.getAs[Double]("disruptionRate") shouldBe 1.0
    weekendRow.getAs[Long]("observations") shouldBe 1L

    val weekdayRow = result.find(!_.getAs[Boolean]("isWeekend")).get
    weekdayRow.getAs[Double]("disruptionRate") shouldBe 0.0
  }

  "weatherCorrelations" should "find a strong positive correlation when severity rises with temperature by design" in {
    val sparkSession = spark
    import sparkSession.implicits._

    val tfl = Seq(
      TflLineStatus("northern", "Northern", 4, "Planned Closure", None, Instant.parse("2026-07-26T12:15:00Z")),
      TflLineStatus("northern", "Northern", 8, "Minor Delays", None, Instant.parse("2026-07-26T13:15:00Z")),
      TflLineStatus("northern", "Northern", 10, "Good Service", None, Instant.parse("2026-07-26T14:15:00Z"))
    ).toDS()

    val weather = Seq(
      WeatherReading(5.0, 3.0, 90, 5.0, "Rain", "heavy rain", Some(4.0), None, Instant.parse("2026-07-26T12:00:00Z")),
      WeatherReading(15.0, 14.0, 60, 2.0, "Clouds", "overcast", None, None, Instant.parse("2026-07-26T13:00:00Z")),
      WeatherReading(25.0, 24.5, 30, 1.0, "Clear", "clear sky", None, None, Instant.parse("2026-07-26T14:00:00Z"))
    ).toDS()

    val result = SeverityAnalysis.weatherCorrelations(tfl, weather).collect()

    val tempCorrelation = result.find(_.getAs[String]("weatherVariable") == "avgTempC").get
      .getAs[Double]("pearsonCorrelation")

    tempCorrelation should be > 0.9
  }
}