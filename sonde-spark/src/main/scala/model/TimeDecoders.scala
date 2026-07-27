package com.milloevers.sonde.model

import io.circe.Decoder

import java.time.{Instant, LocalDateTime, ZoneOffset}

object TimeDecoders {
  implicit val instantDecoder: Decoder[Instant] =
    Decoder.decodeOffsetDateTime.map(_.toInstant) or
      Decoder.decodeLocalDateTime.map(_.toInstant(ZoneOffset.UTC))
}