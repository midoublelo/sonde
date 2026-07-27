package com.milloevers.sonde.model

import io.circe.Decoder
import com.milloevers.sonde.model.TimeDecoders._

import java.time.Instant

final case class TflLineStatus(
    lineId: String,
    lineName: String,
    statusSeverity: Int,
    statusDescription: String,
    reason: Option[String],
    polledAt: Instant
)

object TflLineStatus {
  implicit val decoder: Decoder[TflLineStatus] = Decoder.forProduct6(
    "line_id",
    "line_name",
    "status_severity",
    "status_description",
    "reason",
    "polled_at"
  )(TflLineStatus.apply)
}