package com.milloevers.sonde.ingest

import io.circe.Decoder
import io.circe.parser.decode
import org.apache.spark.sql.{Dataset, Encoder, SparkSession}
import org.slf4j.LoggerFactory

import scala.reflect.ClassTag

object JsonlLoader {

  private val logger = LoggerFactory.getLogger(getClass)

  def load[A: Encoder: ClassTag](spark: SparkSession, path: String)(implicit decoder: Decoder[A]): Dataset[A] = {

    val decoded = spark.sparkContext
      .textFile(path)
      .map(line => decode[A](line))
      .cache()

    val failureCount = decoded.filter(_.isLeft).count()

    if (failureCount > 0) {
      logger.warn(s"Failed to decode $failureCount line(s) from '$path'")
      decoded
        .filter(_.isLeft)
        .take(5)
        .foreach {
          case Left(err) => logger.warn(s"  sample decode failure: ${err.getMessage}")
          case Right(_)  => ()
        }
    }

    val successes = decoded.flatMap(_.toOption)
    spark.createDataset(successes)
  }
}