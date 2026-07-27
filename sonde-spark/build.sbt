ThisBuild / scalaVersion := "2.13.18"
ThisBuild / version      := "0.1.0-SNAPSHOT"
ThisBuild / organization := "com.milloevers"

val jdk21Path = file("C:/Program Files/Java/jdk-21")

ThisBuild / javaHome := {
  if (jdk21Path.exists()) Some(jdk21Path)
  else None // falls back to ambient JAVA_HOME if the path above is wrong
}

run / fork := true
Test / fork := true

val sparkVersion = "4.1.2"

lazy val root = (project in file("."))
  .settings(
    name := "sonde-spark",

    libraryDependencies ++= Seq(
      "org.scala-lang" % "scala-reflect" % scalaVersion.value,

      "org.apache.spark" %% "spark-core" % sparkVersion,
      "org.apache.spark" %% "spark-sql"  % sparkVersion,

      "io.circe" %% "circe-core"    % "0.14.10",
      "io.circe" %% "circe-generic" % "0.14.10",
      "io.circe" %% "circe-parser"  % "0.14.10",

      // testing
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),

    assembly / assemblyMergeStrategy := {
      case PathList("META-INF", xs @ _*) => MergeStrategy.discard
      case _                             => MergeStrategy.first
    }
  )
