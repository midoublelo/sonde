package com.milloevers.sonde.analysis

import com.milloevers.sonde.model.{TflLineStatus, WeatherReading}
import org.apache.spark.sql.{DataFrame, Dataset}
import org.apache.spark.sql.functions._
import org.slf4j.LoggerFactory

object SeverityAnalysis {

  private val logger = LoggerFactory.getLogger(getClass)

  // TfL's statusSeverity is a category code, not a linear "worse to better"
  // scale — code 20 ("Service Closed") sits numerically above 10
  // ("Good Service") despite meaning something different in kind (most
  // likely a routine overnight closure), not "better than good service".
  // Including it would skew averages upward for lines with more logged
  // closures, without that reflecting anything about actual reliability.
  // So it's excluded from both aggregations below — this is a real
  // disruption/severity analysis, and scheduled closures aren't disruption.
  private val ServiceClosedCode = 20

  private def excludingServiceClosed(tfl: Dataset[TflLineStatus]): Dataset[TflLineStatus] =
    tfl.filter(col("statusSeverity") =!= ServiceClosedCode)

  /** Average status_severity per line, across all polled records
   * (excluding "Service Closed" — see ServiceClosedCode above).
   */
  def avgSeverityByLine(tfl: Dataset[TflLineStatus]): DataFrame =
    excludingServiceClosed(tfl)
      .groupBy("lineId")
      .agg(
        avg("statusSeverity").as("avgSeverity"),
        count("*").as("recordCount")
      )
      .orderBy(desc("avgSeverity"))

  /** Joins TfL status records to weather readings by truncating both sides'
   * timestamps to the same hourly bucket (the two feeds don't poll on
   * exactly the same schedule, so an exact-timestamp join would match
   * almost nothing), then averages severity per weather condition
   * (excluding "Service Closed" — see ServiceClosedCode above).
   *
   * CAVEAT: if TfL polls more frequently than weather within a given hour,
   * this join fans out — each TfL record in that hour matches the same
   * single weather reading, so hours with more TfL polls get proportionally
   * more weight in the resulting average. Fine for an exploratory first
   * pass; worth revisiting (e.g. weighting by distinct hour rather than
   * by raw record count) if polling frequency turns out to be very uneven.
   */
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

  /** Every distinct (statusSeverity, statusDescription) pairing seen in the
   * data, ordered by severity. Worth running before trusting any average-
   * severity numbers — TfL's real severity scale includes codes outside
   * the "6 = Severe Delays ... 10 = Good Service" range you'd guess from
   * a handful of samples (e.g. codes for "Special Service", planned
   * closures, etc.), so an average alone can be misleading without seeing
   * which codes actually occur and what they mean.
   */
  def distinctSeverityCodes(tfl: Dataset[TflLineStatus]): DataFrame =
    tfl
      .select("statusSeverity", "statusDescription")
      .distinct()
      .orderBy("statusSeverity")

  /** Pearson correlation between average severity and each continuous
   * weather variable, one row per hour.
   *
   * Both sides are aggregated to a single row per hourBucket *before*
   * joining and correlating. Correlating directly on the raw joined
   * records (many TfL records per hour all sharing one weather reading)
   * would be pseudo-replication — it makes the correlation look far more
   * precise than the underlying data actually supports, since it's not
   * really N independent observations. Aggregating first gives one
   * legitimate observation per hour.
   *
   * rain1hMm / snow1hMm nulls are treated as 0 (no precipitation), per
   * the WeatherReading schema notes — not "missing data".
   *
   * IMPORTANT — sign interpretation: after excluding Service Closed,
   * remaining statusSeverity values run low = worse (2 = Suspended) to
   * high = better (10 = Good Service). So a POSITIVE correlation here
   * means that weather variable is associated with BETTER service, not
   * worse — the opposite of what "correlates with severity" might
   * suggest intuitively. Double-check sign before drawing conclusions.
   *
   * Also worth remembering: correlation, not causation, and with only a
   * modest number of distinct hours in the data so far, treat these as
   * exploratory rather than conclusive.
   */
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

    // A column with zero variance (e.g. avgSnow1hMm if there was no snow
    // at all in the data) makes Pearson correlation mathematically
    // undefined — division by a standard deviation of 0. Older Spark
    // versions quietly returned NaN for this; Spark 4.x's default ANSI
    // mode instead throws DIVIDE_BY_ZERO and crashes the job. So each
    // column's variance is checked first, and zero-variance columns are
    // skipped (with a log message) rather than attempting an undefined
    // correlation.
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