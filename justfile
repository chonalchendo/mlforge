docker := require("docker")
rm := require("rm")
uv := require("uv")


PACKAGE := "mlforge"
REPOSITORY := "mlforge"
SOURCES := "src"
TESTS := "tests"

default:
    @just --list

import "tasks/check.just"
import "tasks/commit.just"
import "tasks/docker.just"
import "tasks/format.just"
import "tasks/install.just"
